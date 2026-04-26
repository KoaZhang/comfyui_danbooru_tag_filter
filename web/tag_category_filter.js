import { app } from "../../scripts/app.js";

const NODE_NAME = "DanbooruTagCategoryFilter";
const UNKNOWN_CATEGORY = "Unknown";
const PANEL_LEFT = 8;
const PANEL_TOP = 108;
const PANEL_RIGHT = 8;
const PANEL_BOTTOM = 12;
const MIN_NODE_WIDTH = 280;
const MIN_PANEL_HEIGHT = 118;

const domPanels = new Map();
let stylesInjected = false;
let layoutLoopStarted = false;

function isTargetNode(node) {
    if (!node) {
        return false;
    }

    return (
        node.comfyClass === NODE_NAME ||
        node.type === NODE_NAME ||
        node.constructor?.comfyClass === NODE_NAME ||
        node.constructor?.type === NODE_NAME
    );
}

function hideWidget(widget) {
    if (!widget || widget.__dtfHidden) {
        return;
    }

    widget.__dtfHidden = true;
    widget.computeSize = () => [0, -4];
    widget.draw = () => {};
    widget.serializeValue = () => widget.value;
    widget.type = "dtf_hidden";
    widget.hidden = true;
}

function injectStyles() {
    if (stylesInjected) {
        return;
    }

    const style = document.createElement("style");
    style.textContent = `
        .dtf-panel {
            position: fixed;
            z-index: 30;
            pointer-events: auto;
            transform-origin: top left;
            box-sizing: border-box;
            border-radius: 12px;
            border: 1px solid #353d4c;
            background: linear-gradient(180deg, #1b1f29 0%, #151922 100%);
            box-shadow: 0 10px 26px rgba(0, 0, 0, 0.25);
            padding: 10px 10px 12px;
            color: #d8deeb;
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            user-select: none;
        }

        .dtf-panel.is-hidden {
            display: none;
        }

        .dtf-help {
            margin: 0 0 10px;
            font-size: 12px;
            line-height: 1.2;
            color: #d0d6e2;
        }

        .dtf-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: flex-start;
        }

        .dtf-pill {
            appearance: none;
            border: 1px solid #565e72;
            background: linear-gradient(180deg, #2b3140 0%, #222734 100%);
            color: #c0c8d6;
            border-radius: 999px;
            padding: 5px 14px;
            font-size: 13px;
            line-height: 1;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease, box-shadow 120ms ease;
        }

        .dtf-pill:hover {
            border-color: #7a859d;
            color: #edf2ff;
        }

        .dtf-pill.is-selected {
            background: linear-gradient(180deg, #2f7cff 0%, #215fd3 100%);
            border-color: #8ac1ff;
            color: #ffffff;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18), 0 0 0 1px rgba(83, 145, 255, 0.16);
        }
    `;
    document.head.appendChild(style);
    stylesInjected = true;
}

function parseCategoryList(rawValue) {
    if (!rawValue) {
        return [];
    }

    try {
        const parsed = JSON.parse(rawValue);
        return Array.isArray(parsed) ? parsed.map((item) => String(item)) : [];
    } catch (error) {
        console.warn("[DanbooruTagCategoryFilter] Failed to parse category list:", error);
        return [];
    }
}

function getBackingWidget(node, name) {
    return node.widgets?.find((widget) => widget.name === name) ?? null;
}

function getKeepUnclassifiedValue(node) {
    return Boolean(getBackingWidget(node, "keep_unclassified")?.value);
}

function getDefaultSelection(categories, keepUnclassified) {
    return categories.filter((category) => category !== UNKNOWN_CATEGORY || keepUnclassified);
}

function syncSelectedValue(node, panelState) {
    const backingWidget = getBackingWidget(node, "selected_categories_json");
    const encoded = JSON.stringify(panelState.selectedCategories);
    if (backingWidget) {
        backingWidget.value = encoded;
        if (typeof backingWidget.callback === "function") {
            backingWidget.callback(encoded);
        }
    }

    node.properties = node.properties || {};
    node.properties.selected_categories = [...panelState.selectedCategories];
    node.properties.selected_categories_json = encoded;
    node.properties.__dtfSelectionTouched = Boolean(panelState.selectionTouched);
    if (Array.isArray(node.widgets_values)) {
        const index = node.widgets?.indexOf(backingWidget);
        if (index >= 0) {
            node.widgets_values[index] = encoded;
        }
    }
    node.setDirtyCanvas(true, true);
}

function ensureNodeSize(node, panelState) {
    const width = Math.max(node.size?.[0] || MIN_NODE_WIDTH, MIN_NODE_WIDTH);
    const panelWidth = Math.max(width - PANEL_LEFT - PANEL_RIGHT, 180);
    if (panelState.root.style.width !== `${panelWidth}px`) {
        panelState.root.style.width = `${panelWidth}px`;
    }

    const measuredHeight = Math.max(panelState.root.offsetHeight || MIN_PANEL_HEIGHT, MIN_PANEL_HEIGHT);
    panelState.panelHeight = measuredHeight;
    const desiredHeight = PANEL_TOP + measuredHeight + PANEL_BOTTOM;
    if (!node.size || node.size[0] !== width || node.size[1] < desiredHeight) {
        node.setSize([width, desiredHeight]);
    }
}

function ensureManagedNode(node) {
    if (!isTargetNode(node)) {
        return null;
    }

    for (const widget of node.widgets || []) {
        if (widget.name === "selected_categories_json" || widget.name === "available_categories_json") {
            hideWidget(widget);
        }
    }

    let panelState = node.__dtfPanelState;
    if (!panelState) {
        panelState = createDomPanel(node);
        node.__dtfPanelState = panelState;
    }

    if (!node.__dtfSpacerAdded && typeof node.addCustomWidget === "function") {
        addSpacerWidget(node, panelState);
        node.__dtfSpacerAdded = true;
    }

    const categoriesWidget = getBackingWidget(node, "available_categories_json");
    if (categoriesWidget?.value) {
        node.properties = node.properties || {};
        node.properties.available_categories_json = categoriesWidget.value;
    }

    loadSelectionState(node, panelState);
    return panelState;
}

function createDomPanel(node) {
    injectStyles();

    const existing = domPanels.get(node.id);
    if (existing) {
        if (!document.body.contains(existing.root)) {
            document.body.appendChild(existing.root);
        }
        return existing;
    }

    const root = document.createElement("div");
    root.className = "dtf-panel is-hidden";
    root.dataset.nodeId = String(node.id);

    const help = document.createElement("div");
    help.className = "dtf-help";
    help.textContent = "Double-click categories to keep them";
    root.appendChild(help);

    const grid = document.createElement("div");
    grid.className = "dtf-grid";
    root.appendChild(grid);

    document.body.appendChild(root);

    const state = {
        node,
        root,
        grid,
        help,
        categories: [],
        selectedCategories: [],
        selectionTouched: false,
        buttons: new Map(),
        panelHeight: MIN_PANEL_HEIGHT,
    };

    root.addEventListener("mousedown", (event) => {
        event.stopPropagation();
    });

    domPanels.set(node.id, state);
    return state;
}

function removeDomPanel(node) {
    const state = domPanels.get(node.id);
    if (!state) {
        return;
    }

    state.root.remove();
    domPanels.delete(node.id);
}

function cleanupOrphanPanels() {
    const liveIds = new Set((app.graph?._nodes || []).map((graphNode) => String(graphNode.id)));
    for (const [nodeId, state] of domPanels.entries()) {
        const nodeObject = app.graph?.getNodeById?.(Number(nodeId)) || app.graph?.getNodeById?.(nodeId);
        if (!liveIds.has(String(nodeId)) || !nodeObject) {
            state.root.remove();
            domPanels.delete(nodeId);
            continue;
        }

        if (!document.body.contains(state.root)) {
            document.body.appendChild(state.root);
        }
    }
}

function reconcileManagedNodes() {
    for (const node of app.graph?._nodes || []) {
        if (!isTargetNode(node)) {
            continue;
        }

        const panelState = ensureManagedNode(node);
        if (panelState && !document.body.contains(panelState.root)) {
            document.body.appendChild(panelState.root);
        }
    }
}

function renderButtons(panelState) {
    panelState.grid.replaceChildren();
    panelState.buttons.clear();

    for (const category of panelState.categories) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dtf-pill";
        button.textContent = category;
        button.dataset.category = category;
        button.addEventListener("dblclick", (event) => {
            event.preventDefault();
            event.stopPropagation();
            toggleCategory(panelState.node, panelState, category);
        });
        button.addEventListener("mousedown", (event) => {
            event.stopPropagation();
        });

        panelState.grid.appendChild(button);
        panelState.buttons.set(category, button);
    }

    updateButtonStyles(panelState);
}

function updateButtonStyles(panelState) {
    const selected = new Set(panelState.selectedCategories);
    for (const [category, button] of panelState.buttons.entries()) {
        button.classList.toggle("is-selected", selected.has(category));
    }
}

function loadSelectionState(node, panelState) {
    const categoriesWidget = getBackingWidget(node, "available_categories_json");
    const selectionWidget = getBackingWidget(node, "selected_categories_json");
    const categories = parseCategoryList(categoriesWidget?.value || node.properties?.available_categories_json);
    panelState.categories = categories;

    const widgetValue =
        typeof selectionWidget?.value === "string" && selectionWidget.value.trim()
            ? selectionWidget.value.trim()
            : typeof node.properties?.selected_categories_json === "string"
              ? node.properties.selected_categories_json.trim()
              : "";
    if (widgetValue) {
        panelState.selectedCategories = parseCategoryList(widgetValue).filter((category) => categories.includes(category));
        panelState.selectionTouched = true;
    } else if (Array.isArray(node.properties?.selected_categories)) {
        panelState.selectedCategories = node.properties.selected_categories.filter((category) => categories.includes(category));
        panelState.selectionTouched = Boolean(node.properties?.__dtfSelectionTouched);
    } else {
        panelState.selectedCategories = getDefaultSelection(categories, getKeepUnclassifiedValue(node));
        panelState.selectionTouched = false;
    }

    if (!panelState.selectedCategories.length && categories.length) {
        panelState.selectedCategories = getDefaultSelection(categories, getKeepUnclassifiedValue(node));
        panelState.selectionTouched = false;
    }

    renderButtons(panelState);
    syncSelectedValue(node, panelState);
    ensureNodeSize(node, panelState);
}

function toggleCategory(node, panelState, category) {
    const selected = new Set(panelState.selectedCategories);
    if (selected.has(category)) {
        selected.delete(category);
    } else {
        selected.add(category);
    }

    panelState.selectedCategories = panelState.categories.filter((item) => selected.has(item));
    panelState.selectionTouched = true;
    updateButtonStyles(panelState);
    syncSelectedValue(node, panelState);
}

function updatePanelPosition(panelState) {
    const { node, root } = panelState;
    const canvas = app.canvas?.canvas;
    const ds = app.canvas?.ds;
    const nodeStillExists = Boolean(app.graph?.getNodeById?.(node.id));
    if (!nodeStillExists) {
        removeDomPanel(node);
        return;
    }

    if (!document.body.contains(root)) {
        document.body.appendChild(root);
    }

    if (!canvas || !ds || !document.body.contains(canvas) || !document.body.contains(root)) {
        root.classList.add("is-hidden");
        return;
    }

    if (node.flags?.collapsed || node.mode === 4) {
        root.classList.add("is-hidden");
        return;
    }

    ensureNodeSize(node, panelState);

    const rect = canvas.getBoundingClientRect();
    const scale = ds.scale || 1;
    const left = rect.left + window.scrollX + (node.pos[0] + ds.offset[0] + PANEL_LEFT) * scale;
    const top = rect.top + window.scrollY + (node.pos[1] + ds.offset[1] + PANEL_TOP) * scale;
    const width = Math.max(node.size[0] - PANEL_LEFT - PANEL_RIGHT, 180);

    root.style.width = `${width}px`;
    root.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
    root.classList.remove("is-hidden");
}

function startLayoutLoop() {
    if (layoutLoopStarted) {
        return;
    }

    layoutLoopStarted = true;
    const tick = () => {
        reconcileManagedNodes();
        cleanupOrphanPanels();
        for (const panelState of domPanels.values()) {
            updatePanelPosition(panelState);
        }
        window.requestAnimationFrame(tick);
    };
    window.requestAnimationFrame(tick);
}

function addSpacerWidget(node, panelState) {
    const widget = {
        type: "dtf_dom_spacer",
        name: "category_picker",
        value: "",
        options: {},
        computeSize(width) {
            const panelWidth = Math.max(width - PANEL_LEFT - PANEL_RIGHT, 180);
            if (panelState.root.style.width !== `${panelWidth}px`) {
                panelState.root.style.width = `${panelWidth}px`;
            }

            panelState.panelHeight = Math.max(panelState.root.offsetHeight || MIN_PANEL_HEIGHT, MIN_PANEL_HEIGHT);
            return [width, panelState.panelHeight + 8];
        },
        draw() {
            ensureNodeSize(node, panelState);
            return panelState.panelHeight + 8;
        },
    };

    node.addCustomWidget(widget);
}

app.registerExtension({
    name: "Danbooru.TagCategoryFilter",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== NODE_NAME) {
            return;
        }

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function onNodeCreatedWrapped() {
            const result = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
            const panelState = ensureManagedNode(this);

            const keepWidget = getBackingWidget(this, "keep_unclassified");
            if (keepWidget) {
                const originalCallback = keepWidget.callback;
                keepWidget.callback = (...args) => {
                    if (originalCallback) {
                        originalCallback.apply(keepWidget, args);
                    }
                    const managedPanel = ensureManagedNode(this);
                    if (managedPanel && !managedPanel.selectionTouched) {
                        loadSelectionState(this, managedPanel);
                    }
                };
            }

            startLayoutLoop();
            return result;
        };

        const onConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function onConfigureWrapped(info) {
            const result = onConfigure ? onConfigure.apply(this, arguments) : undefined;
            ensureManagedNode(this);
            startLayoutLoop();
            return result;
        };

        const onRemoved = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function onRemovedWrapped() {
            removeDomPanel(this);
            return onRemoved ? onRemoved.apply(this, arguments) : undefined;
        };
    },
});
