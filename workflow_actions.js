import { app } from "../../../scripts/app.js";


const KRITA_SAVE_IMAGE_NODE_TYPE = "KritaSaveImage-15347";
const DOCUMENT_WIDGET_LABEL = "document";
const META_WIDGET_LABEL = "_meta-15347";
const KRITA_DOCUMENT_GRAPH_USAGE_REFRESH_RATE = 300;
export const COMFY_TABS_CONTAINER_SELECTOR = ".workflow-tabs-container";
export const COMFY_ACTIVE_TAB_SELECTOR = '[role="tab"][aria-selected="true"] .workflow-label';
const KRITA_CUSTOM_IO_NODE_TYPES = [
    KRITA_SAVE_IMAGE_NODE_TYPE
];
const EXTENSION_NAME = "Krita.WorkflowSync";

let baseUrl = null;
let previousTabName = null;
let previousDocumentIdLists = {};
let websocketRoutesSetup = false;
const kritaNodeStateCache = new Map();
const kritaNodeStateEventRevisions = new Map();


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
        applyCachedKritaNodeStates();
    },
};


export function fixKritaNodeUi(node) {
    if(node.type && !KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type)) return;

    const metaWidget = node.widgets?.find(w => w.label === META_WIDGET_LABEL);
    const metaSlot = node.inputs.find(i => i.name === META_WIDGET_LABEL);
    const documentSlot = node.inputs.find(i => i.name === DOCUMENT_WIDGET_LABEL);
    if(documentSlot) {
        const slotIndex = node.inputs.indexOf(documentSlot);
        node.inputs.splice(slotIndex, 1);
    }
    if(metaSlot) {
        const slotIndex = node.inputs.indexOf(metaSlot);
        node.inputs.splice(slotIndex, 1);
    }
    if(metaWidget) {
        metaWidget.hidden = true;
    }

    if(node.subgraph) {
        for(const subnode of node.subgraph.nodes) {
            fixKritaNodeUi(subnode);
        }
    }
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
    if(!state || state.type !== KRITA_SAVE_IMAGE_NODE_TYPE || !state.document_id) return;

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
            if(state.type !== KRITA_SAVE_IMAGE_NODE_TYPE || !state.document_id) continue;

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
        const documentWidget = node.widgets?.find(w => w.label === DOCUMENT_WIDGET_LABEL);
        const metaWidget = node.widgets?.find(w => w.label === META_WIDGET_LABEL);
        if(!metaWidget) continue;

        const documentId = documentWidget?.value;
        const state = documentId
            ? kritaNodeStateCache.get(kritaNodeStateKey(documentId, node.id, node.type))
            : null;

        if(state) {
            setNodeMetadataValue(node, metaWidget, state);
            continue;
        }

        if(metaWidget.value) {
            setNodeMetadataValue(node, metaWidget, "");
        }
    }
}


function setNodeMetadataValue(node, widget, value) {
    const serialized = typeof value === "string" ? value : JSON.stringify(value);
    if(widget.value === serialized) return;

    widget.value = serialized;
    node.graph?.change?.();
    node.setDirtyCanvas?.(true, true);
}


export async function updateDocumentWidgetValues(documentNames=null) {
    const internalKritaNodes = getInternalKritaNodes();

    if(documentNames === null) documentNames = (await api.get('/krita/documents')).documents;

    for(const node of internalKritaNodes) {
        const dropdownWidget = node.widgets.find(w => w.label === DOCUMENT_WIDGET_LABEL);
        if(!dropdownWidget) {
            console.warn(`Could not find document widget in krita node: ${node}.`);
            continue;
        }

        const array = dropdownWidget.options.values;
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
    return tabElements?.innerHTML ?? previousTabName;
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


export function getInternalKritaNodes() {
    const internalKritaNodes = [];
    const nodes = getGraphNodesRecursive();

    for(const node of nodes) {
        if(KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type)) {
            internalKritaNodes.push(node);
        }
    }

    return internalKritaNodes;
}


export function generateActiveKritaNodes() {
    const kritaNodes = [];
    const customKritaNodeFactory = new CustomKritaNodeFactory();

    const nodePairs = getGraphNodesRecursive();

    for(const internalNode of nodePairs) {
        if(!KRITA_CUSTOM_IO_NODE_TYPES.includes(internalNode.type)) continue;
        if(internalNode.mode !== 0) continue;

        const customKritaNode = customKritaNodeFactory.create(internalNode);
        kritaNodes.push(customKritaNode.dump());
    }

    return kritaNodes;
}


export function getGraphNodesRecursive(rootGraph) {
    if(!rootGraph) rootGraph = app.graph;

    const nodes = [];
    for(const node of rootGraph.nodes) {
        nodes.push(node);
        if(node.subgraph) getGraphNodesRecursive(node.subgraph).forEach(n => nodes.push(n));
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
