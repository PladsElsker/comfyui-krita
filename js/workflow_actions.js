import { app } from "../../../scripts/app.js";


(() => {
    const KRITA_SAVE_IMAGE_NODE_TYPE = "KritaSaveImage-15347";
    const DOCUMENT_WIDGET_LABEL = "document";
    const META_WIDGET_LABEL = "_meta-15347";
    const KRITA_DOCUMENT_GRAPH_USAGE_REFRESH_RATE = 300;
    const COMFY_TABS_CONTAINER_SELECTOR = ".workflow-tabs-container";
    const COMFY_ACTIVE_TAB_SELECTOR = ".p-togglebutton.p-component.p-togglebutton-checked .workflow-label";
    const KRITA_CUSTOM_IO_NODE_TYPES = [
        KRITA_SAVE_IMAGE_NODE_TYPE
    ];


    const kritaNodes = [];
    let baseUrl = null;
    let previousTabName = null;
    let previousUsedDocumentIdsInGraph = {};


    const api = (() => {
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


    const extension = { 
        name: "Krita.WorkflowSync",
        async afterConfigureGraph() {
            await updateKritaNodeDocuments();
            await setupAdditionalWebsocketRoutes();
            await setupWorkflowSynchronization();

            for(const node of app.graph._nodes) {
                fixKritaNodeUi(node);
            }
        },
        async nodeCreated(node) {
            console.log(node);
            fixKritaNodeUi(node);
        },
    };


    function fixKritaNodeUi(node) {
        if(node.type && !KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type)) return;

        const metaWidget = node.widgets.find(w => w.label === META_WIDGET_LABEL);
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
    }


    function setupAdditionalWebsocketRoutes() {
        app.api.socket.addEventListener('message', event => {
            const data = JSON.parse(event.data);
            switch(data.type) {
                case "krita::documents::update":
                    updateKritaNodeDocuments(data.data.documents);
            }
        });
    }


    async function updateKritaNodeDocuments(documentNames=null) {
        updateKritaNodes()

        if(documentNames === null) documentNames = (await api.get('/krita/documents')).documents;

        for(const node of kritaNodes) {
            const dropdownWidget = node.widgets.find(w => w.label === DOCUMENT_WIDGET_LABEL);
            if(!dropdownWidget) {
                console.warn(`Could not find dropdown widget in krita node: ${node}.`);
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
    }

    async function setupWorkflowSynchronization() {
        await sendWorkflow();

        window.addEventListener("focus", () => sendWorkflow(true));

        (function asyncRecurse() {
            sendWorkflow();
            setTimeout(asyncRecurse, KRITA_DOCUMENT_GRAPH_USAGE_REFRESH_RATE);
        })();
    }


    async function sendWorkflow(skipCondition=false) {
        const tabGroupElement = document.querySelector(COMFY_TABS_CONTAINER_SELECTOR);
        const tabElements = tabGroupElement?.querySelector(COMFY_ACTIVE_TAB_SELECTOR);
        const tabName = tabElements?.innerHTML ?? previousTabName;
        if(!tabName) return;

        const documentIdLists = {};

        updateKritaNodes();

        for(const node of kritaNodes) {
            const documentWidget = node.widgets.find(w => w.label === DOCUMENT_WIDGET_LABEL);

            if(!documentWidget) {
                console.warn("Could not find dropdown widget in krita document node.");
                continue;
            }
            
            const widgetIndex = node.widgets.indexOf(documentWidget);
            const value = node.widgets_values[widgetIndex];
            if(!(value in documentIdLists)) documentIdLists[value] = []
            documentIdLists[value].push(JSON.stringify({
                id: node.id,
                type: node.type,
            }));
        }

        if(
            !skipCondition &&
            Object.entries(documentIdLists).every(([documentId, nodes]) => haveSameElements(previousUsedDocumentIdsInGraph[documentId], nodes)) && 
            Object.entries(previousUsedDocumentIdsInGraph).every(([documentId, nodes]) => haveSameElements(documentIdLists[documentId], nodes)) && 
            (previousTabName === tabName)
        ) return;

        Object.entries(documentIdLists).forEach(([documentId, nodes]) => {
            const workflowResponse = {
                name: tabName, 
                workflow: {
                    nodes: nodes.map(JSON.parse),
                },
            };
            return api.put(`/krita/documents/${documentId}/workflow`, workflowResponse)
        });

        previousUsedDocumentIdsInGraph = documentIdLists;
        previousTabName = tabName;
    }


    function haveSameElements(a, b) {
        return a?.length === b?.length && a?.every(v => b?.includes(v));
    }


    function wsToHttpBase(wsUrl) {
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


    function updateKritaNodes() {
        kritaNodes.splice(0, kritaNodes.length);
        const nodes = app.graph._nodes;

        for(const node of nodes) {
            if(KRITA_CUSTOM_IO_NODE_TYPES.includes(node.type)) {
                kritaNodes.push(node);
            }
        }
    }


    app.registerExtension(extension);
})();
