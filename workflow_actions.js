import { app } from "../../../scripts/app.js";


const KRITA_SAVE_IMAGE_NODE_TYPE = "KritaSaveImage-15347";
const KRITA_LOAD_IMAGE_NODE_TYPE = "KritaLoadImage-15347";
const DOCUMENT_WIDGET_LABEL = "document";
const META_WIDGET_LABEL = "_meta-15347";
const KRITA_DOCUMENT_GRAPH_USAGE_REFRESH_RATE = 300;
export const COMFY_TABS_CONTAINER_SELECTOR = ".workflow-tabs-container";
export const COMFY_ACTIVE_TAB_SELECTOR = '[role="tab"][aria-selected="true"] .workflow-label';
export const KRITA_CUSTOM_IO_NODE_TYPES = [
    KRITA_SAVE_IMAGE_NODE_TYPE,
    KRITA_LOAD_IMAGE_NODE_TYPE,
];

function getMetadataWidgetLabel(nodeType) {
    return KRITA_CUSTOM_IO_NODE_TYPES.includes(nodeType) ? META_WIDGET_LABEL : null;
}

function createDefaultNodeState(node) {
    if(node.type === KRITA_LOAD_IMAGE_NODE_TYPE) {
        return {
            id: node.id,
            type: node.type,
            document_id: "",
            layer_ids: [],
            layer_names: [],
            snapshot_revision: "",
        };
    }

    return {
        id: node.id,
        type: node.type,
        document_id: "",
        insert_direction: "below",
        path: [{ quuid: null, type: "target" }],
        layer_name: "Not set",
    };
}
const EXTENSION_NAME = "Krita.WorkflowSync";

let baseUrl = null;
let previousTabName = null;
let previousDocumentIdLists = {};
let websocketRoutesSetup = false;
const kritaNodeStateCache = new Map();
const kritaNodeStateEventRevisions = new Map();
const kritaLoadImagePreviewRevisions = new WeakMap();
const kritaLoadImagePreviewRequests = new WeakMap();


export const api = (() => {
    async function request(method, route, data) {
        if(baseUrl === null) baseUrl = wsToHttpBase(app.api.socket.url);

        const url = new URL(route, baseUrl).toString();
        
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json'
            },
        };

        if (data) options.body = JSON.stringify(data);
        const response = await fetch(url, options);
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);

        const bodyText = await response.text();
        try {
            return JSON.parse(bodyText);
        }
        catch {
            return bodyText;
        }
    }

    return {
        get: (route) => request('GET', route),
        post: (route, data) => request('POST', route, data),
        put: (route, data) => request('PUT', route, data),
        delete: (route) => request('DELETE', route)
    };
})();


export const extension = { 
    name: EXTENSION_NAME,
    async afterConfigureGraph() {
        for(const node of getGraphNodesRecursive()) {
            fixKritaNodeUi(node);
        }

        setupAdditionalWebsocketRoutes();
        await updateDocumentWidgetValues();
        await loadKritaNodeStates();
        applyCachedKritaNodeStates();
        await sendWorkflow(true);
        await sendWorkflowOnChanges();
    },
    async nodeCreated(node) {
        fixKritaNodeUi(node);
        await updateDocumentWidgetValues();
        applyCachedKritaNodeStates();
    },
};


export function fixKritaNodeUi(node, visitedNodes=new Set()) {
    if(!node || visitedNodes.has(node)) return;
    visitedNodes.add(node);

    const metadataWidgetLabel = getMetadataWidgetLabel(node.type);
    if(metadataWidgetLabel !== null) {
        const inputs = node.inputs ?? [];
        const metaSlot = inputs.find(i => i.name === metadataWidgetLabel);
        const documentSlot = inputs.find(i => i.name === DOCUMENT_WIDGET_LABEL);

        if(documentSlot) inputs.splice(inputs.indexOf(documentSlot), 1);
        if(metaSlot) inputs.splice(inputs.indexOf(metaSlot), 1);
        hideKritaMetadataWidget(node, metadataWidgetLabel);
    }

    // Ordinary ComfyUI nodes can own subgraphs that contain Krita nodes.
    for(const subnode of (node.subgraph?.nodes ?? [])) {
        fixKritaNodeUi(subnode, visitedNodes);
    }
}


function findKritaWidget(node, name) {
    return node.widgets?.find(widget =>
        widget.name === name || widget.label === name
    ) ?? null;
}


function hideKritaMetadataWidget(node, label=getMetadataWidgetLabel(node.type)) {
    if(label === null) return;
    const widget = findKritaWidget(node, label);
    if(!widget) return;

    // V3 schema-level hidden flag is authoritative; keep matching widget flags
    // here for workflows loaded from older node definitions.
    widget.options = widget.options ?? {};
    widget.hidden = true;
    widget.options.hidden = true;
    node.setDirtyCanvas?.(true, true);
}


export function setupAdditionalWebsocketRoutes() {
    if(websocketRoutesSetup) return;
    websocketRoutesSetup = true;

    app.api.socket.addEventListener('message', async event => {
        if(typeof event.data !== "string") return;

        try {
            const data = JSON.parse(event.data);
            switch(data.type) {
                case "krita::documents::update":
                    await updateDocumentWidgetValues(data.data.documents);
                    await sendWorkflow();
                    break;
                case "krita::nodes::update":
                    if(data.data.deleted) {
                        removeKritaNodeState(data.data);
                    }
                    else if(data.data.state) {
                        applyKritaNodeState(data.data.state);
                        if(data.data.preview) {
                            await updateKritaLoadImagePreview(data.data.state, data.data.preview);
                        }
                    }
                    break;
            }
        }
        catch(error) {
            console.error("Could not process a Krita integration websocket event", error);
        }
    });
}


function kritaNodeStateKey(documentId, nodeId, nodeType=KRITA_SAVE_IMAGE_NODE_TYPE) {
    return `${documentId}::${nodeType}::${nodeId}`;
}


export function applyKritaNodeState(state) {
    if(!state || !KRITA_CUSTOM_IO_NODE_TYPES.includes(state.type) || !state.document_id) return;

    const key = kritaNodeStateKey(state.document_id, state.id, state.type);
    kritaNodeStateEventRevisions.set(key, (kritaNodeStateEventRevisions.get(key) ?? 0) + 1);
    kritaNodeStateCache.set(key, state);
    applyCachedKritaNodeStates();
}


function removeKritaNodeState(deleted) {
    if(!deleted?.document_id || deleted.id === undefined || !deleted.type) return;

    const key = kritaNodeStateKey(deleted.document_id, deleted.id, deleted.type);
    kritaNodeStateEventRevisions.set(key, (kritaNodeStateEventRevisions.get(key) ?? 0) + 1);
    kritaNodeStateCache.delete(key);
    applyCachedKritaNodeStates();
}


export async function loadKritaNodeStates() {
    const revisionsAtRequest = new Map(kritaNodeStateEventRevisions);
    try {
        const response = await api.get('/krita/nodes/states');
        for(const state of (response.states ?? [])) {
            if(!KRITA_CUSTOM_IO_NODE_TYPES.includes(state.type) || !state.document_id) continue;

            const key = kritaNodeStateKey(state.document_id, state.id, state.type);
            if((kritaNodeStateEventRevisions.get(key) ?? 0) !== (revisionsAtRequest.get(key) ?? 0)) continue;

            kritaNodeStateCache.set(key, state);
        }
        applyCachedKritaNodeStates();
    }
    catch(error) {
        console.error("Could not load the current Krita output-node state", error);
    }
}


export function applyCachedKritaNodeStates() {
    for(const node of getInternalKritaNodes()) {
        const documentWidget = findKritaWidget(node, DOCUMENT_WIDGET_LABEL);
        const metadataLabel = getMetadataWidgetLabel(node.type);
        const metaWidget = metadataLabel === null ? null : findKritaWidget(node, metadataLabel);
        hideKritaMetadataWidget(node, metadataLabel);
        if(!metaWidget) continue;

        const documentId = documentWidget?.value;
        const state = documentId
            ? kritaNodeStateCache.get(kritaNodeStateKey(documentId, node.id, node.type))
            : null;

        if(state) {
            setNodeMetadataValue(node, metaWidget, state);
            continue;
        }

        setNodeMetadataValue(node, metaWidget, createDefaultNodeState(node));
    }
}


function setNodeMetadataValue(node, widget, value) {
    // Layer IDs and names are Krita-side UI state, not execution inputs.
    // Only the canonical pixel digest participates in ComfyUI's cache key.
    const executionState = node.type === KRITA_LOAD_IMAGE_NODE_TYPE
        ? {
            id: value.id,
            type: value.type,
            document_id: value.document_id,
            snapshot_revision: value.snapshot_revision,
        }
        : value;
    const serialized = typeof executionState === "string"
        ? executionState
        : JSON.stringify(executionState);
    if(widget.value === serialized) return;

    widget.value = serialized;
    node.graph?.change?.();
    node.setDirtyCanvas?.(true, true);
}


function getKritaNodeLocatorId(node) {
    const localId = String(node.id);
    const graph = node.graph;
    if(!graph || graph === app.graph) return localId;
    const graphId = graph.id;
    return graphId ? `${graphId}:${localId}` : localId;
}


async function updateKritaLoadImagePreview(state, preview) {
    if(
        state?.type !== KRITA_LOAD_IMAGE_NODE_TYPE ||
        !state.snapshot_revision ||
        !preview?.filename ||
        baseUrl === null
    ) return;

    const node = getInternalKritaNodes().find(candidate => {
        if(candidate.id !== state.id || candidate.type !== KRITA_LOAD_IMAGE_NODE_TYPE) return false;
        return findKritaWidget(candidate, DOCUMENT_WIDGET_LABEL)?.value === state.document_id;
    });
    if(!node) return;

    if(kritaLoadImagePreviewRevisions.get(node) === state.snapshot_revision) return;

    // A later snapshot supersedes any preview fetch already in flight.
    const requestId = (kritaLoadImagePreviewRequests.get(node) ?? 0) + 1;
    kritaLoadImagePreviewRequests.set(node, requestId);
    const params = new URLSearchParams({
        filename: preview.filename,
        subfolder: preview.subfolder ?? "",
        type: preview.type ?? "temp",
    });
    const response = await fetch(new URL(`/view?${params.toString()}`, baseUrl), {
        cache: "no-store",
    });
    if(!response.ok) {
        throw new Error(`Could not fetch the updated Krita preview: HTTP ${response.status}`);
    }

    const objectUrl = URL.createObjectURL(await response.blob());
    if(kritaLoadImagePreviewRequests.get(node) !== requestId) {
        URL.revokeObjectURL(objectUrl);
        return;
    }

    const image = new Image();
    image.onload = () => {
        if(
            kritaLoadImagePreviewRequests.get(node) !== requestId ||
            !getInternalKritaNodes().includes(node)
        ) {
            URL.revokeObjectURL(objectUrl);
            return;
        }

        const locatorId = getKritaNodeLocatorId(node);
        const pinia = document.getElementById("vue-app")
            ?.__vue_app__?.config?.globalProperties?.$pinia;
        const nodeOutputStore = pinia?._s?.get?.("nodeOutput");
        if(typeof nodeOutputStore?.setNodePreviewsByLocatorId === "function") {
            // This is ComfyUI's reactive preview store used by its Vue nodes.
            nodeOutputStore.setNodePreviewsByLocatorId(locatorId, [objectUrl]);
            const previousUrl = node._kritaLoadImagePreviewUrl;
            if(previousUrl && previousUrl !== objectUrl) URL.revokeObjectURL(previousUrl);
        }
        else {
            // Legacy LiteGraph canvas preview fallback.
            const previousUrl = node._kritaLoadImagePreviewUrl;
            node.imgs = [image];
            node.images = [{
                filename: preview.filename,
                subfolder: preview.subfolder ?? "",
                type: preview.type ?? "temp",
            }];
            node.imageIndex = 0;
            if(previousUrl && previousUrl !== objectUrl) URL.revokeObjectURL(previousUrl);
        }

        node._kritaLoadImagePreviewUrl = objectUrl;
        if(app.nodePreviewImages) app.nodePreviewImages[locatorId] = [objectUrl];
        node.setDirtyCanvas?.(true, true);
        kritaLoadImagePreviewRevisions.set(node, state.snapshot_revision);
    };
    image.onerror = () => URL.revokeObjectURL(objectUrl);
    image.src = objectUrl;
}


export async function updateDocumentWidgetValues(documentNames=null) {
    const internalKritaNodes = getInternalKritaNodes();

    if(documentNames === null) documentNames = (await api.get('/krita/documents')).documents;

    for(const node of internalKritaNodes) {
        const dropdownWidget = findKritaWidget(node, DOCUMENT_WIDGET_LABEL);
        if(!dropdownWidget) {
            console.warn(`Could not find document widget in krita node: ${node}.`);
            continue;
        }

        dropdownWidget.options = dropdownWidget.options ?? {};
        const array = dropdownWidget.options.values ?? (dropdownWidget.options.values = []);
        array.splice(0, array.length);
        documentNames.forEach(d => array.push(d));
        if(!documentNames.includes(dropdownWidget.value)) {
            dropdownWidget.value = null;
        }
        if(dropdownWidget.value == null && documentNames.length > 0) {
            dropdownWidget.value = documentNames[0]
        }
    }

    applyCachedKritaNodeStates();
}


export async function sendWorkflowOnChanges() {
    window.addEventListener("focus", async () => await sendWorkflow(true));

    (async function asyncRecurse() {
        await sendWorkflow();
        setTimeout(asyncRecurse, KRITA_DOCUMENT_GRAPH_USAGE_REFRESH_RATE);
    })();
}


export async function sendWorkflow(skipCondition=false) {
    applyCachedKritaNodeStates();
    const tabName = getActiveTabName();
    if(!tabName) return;

    const documentIdLists = getDocumentIdsNodeMap();

    const documentIdListsStringified = {};
    Object.entries(documentIdLists).forEach(([documentId, nodes]) => {
        documentIdListsStringified[documentId] = documentIdLists[documentId].map(JSON.stringify);
    });

    const changesDetected = skipCondition ||
        Object.keys(documentIdListsStringified).length !== Object.keys(previousDocumentIdLists).length ||
        Object.entries(documentIdListsStringified).some(([documentId, nodes]) => !haveSameElements(previousDocumentIdLists[documentId], nodes)) ||
        (previousTabName !== tabName);

    if(!changesDetected) return;

    api.put(`/krita/documents/workflows`, {
        name: tabName,
        workflows: documentIdLists,
    });

    previousDocumentIdLists = documentIdListsStringified;
    previousTabName = tabName;
}


export function getActiveTabName() {
    const tabGroupElement = document.querySelector(COMFY_TABS_CONTAINER_SELECTOR);
    const tabElements = tabGroupElement?.querySelector(COMFY_ACTIVE_TAB_SELECTOR);
    return tabElements?.textContent?.trim() ?? previousTabName;
}


export function getDocumentIdsNodeMap() {
    const getDocumentIdsNodeMap = {};

    const kritaNodes = generateActiveKritaNodes();

    for(const node of kritaNodes) {
        for(const documentId of node.documentIds) {
            if(!(documentId in getDocumentIdsNodeMap)) getDocumentIdsNodeMap[documentId] = [];
            getDocumentIdsNodeMap[documentId].push({
                id: node.id,
                type: node.type,
                name: node.name,
            });
        }
    }

    return getDocumentIdsNodeMap;
}


export function haveSameElements(a, b) {
    return a?.length === b?.length && a?.every(v => b?.includes(v));
}


export function wsToHttpBase(wsUrl) {
    const url = new URL(wsUrl);

    if (url.protocol === 'ws:') {
        url.protocol = 'http:';
    } else if (url.protocol === 'wss:') {
        url.protocol = 'https:';
    }

    if (url.pathname.endsWith('/ws')) {
        url.pathname = '/';
        url.search = '';
    }

    return url.origin + url.pathname;
}


export function getInternalKritaNodes(rootGraph=app.graph) {
    return getGraphNodesRecursive(rootGraph).filter(
        node => KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type)
    );
}


export function generateActiveKritaNodes(rootGraph=app.graph) {
    const customKritaNodeFactory = new CustomKritaNodeFactory();

    return getInternalKritaNodes(rootGraph)
        .filter(internalNode => internalNode.mode === 0)
        .map(internalNode => customKritaNodeFactory.create(internalNode).dump());
}


export function getGraphNodesRecursive(rootGraph=app.graph, visitedGraphs=new Set(), visitedNodes=new Set()) {
    if(!rootGraph || visitedGraphs.has(rootGraph)) return [];
    visitedGraphs.add(rootGraph);

    const nodes = [];
    for(const node of (rootGraph.nodes ?? [])) {
        if(!node || visitedNodes.has(node)) continue;
        visitedNodes.add(node);
        nodes.push(node);

        if(node.subgraph) {
            nodes.push(...getGraphNodesRecursive(node.subgraph, visitedGraphs, visitedNodes));
        }
    }

    return nodes;
}


export class CustomKritaNode {
    constructor(id, type, name, documentIds) {
        this.id = id
        this.type = type;
        this.name = name;
        this.documentIds = documentIds;
    }

    dump() {
        return {
            id: this.id,
            type: this.type,
            name: this.name,
            documentIds: this.documentIds,
        }
    }
}


export class CustomKritaNodeFactory {
    create(internalNode) {
        const documentIds = internalNode.widgets
            .map((w, i) => [w, i])
            .filter(([w, _]) => w.label === DOCUMENT_WIDGET_LABEL)
            .map(([_, i]) => internalNode.serialize().widgets_values[i]);

        return new CustomKritaNode(
            internalNode.id,
            internalNode.type,
            internalNode.title,
            documentIds,
        );
    }
}


app.registerExtension(extension);
