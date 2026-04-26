import { app } from "../../scripts/app.js";

const NODE_NAME = "DanbooruTagCategoryFilter";
const DISPLAY_NAME = "Danbooru Tag Category Filter";
const UNKNOWN_CATEGORY = "Unknown";
const PANEL_LEFT = 8;
const PANEL_TOP = 108;
const PANEL_RIGHT = 8;
const PANEL_BOTTOM = 12;
const MIN_NODE_WIDTH = 280;
const MIN_PANEL_HEIGHT = 118;

const domPanels = new Map();
let stylesInjected = false;
let loopStarted = false;

function isTargetNode(node) {
    if (!node) {
        return false;
    }

    const candidates = [
        node.comfyClass,
        node.type,
        node.constructor?.comfyClass,
        node.constructor?.type,
        node.title,
    ].filter(Boolean);

    return candidates.includes(NODE_NAME) || candidates.includes(DISPLAY_NAME);
}

function injectStyles() {
    if (stylesInjected) {
        return;
    }

    const style = document.createElement("style");
    style.textContent = `
        .dtf-panel {
            position: fixed;
            z-index: 40;
            pointer-events: auto;
            transform-origin: top left;
            box-sizing: border-box;
            border-radius: 12px;
            border: 1px solid #32394a;
            background: linear-gradient(180deg, #1a1f29 0%, #141924 100%);
            box-shadow: 0 12px 28px rgba(0, 0, 0, 0.28);
            padding: 9px 10px 11px;
            color: #d8deeb;
            font-family: Inter, "Segoe UI", Arial, sans-serif;
            user-select: none;
        }

        .dtf-panel.is-hidden {
            display: none;
        }

        .dtf-help {
            margin: 0 0 8px;
            font-size: 11px;
            line-height: 1.2;
            color: #aeb8cb;
            letter-spacing: 0.01em;
        }

        .dtf-toolbar {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin: 0 0 8px;
        }

        .dtf-toolbar-actions {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .dtf-mini-btn {
            appearance: none;
            border: 1px solid #495267;
            background: linear-gradient(180deg, #262c37 0%, #1d222d 100%);
            color: #d7e0f3;
            border-radius: 999px;
            padding: 3px 10px;
            font-size: 11px;
            line-height: 1.1;
            font-weight: 700;
            cursor: pointer;
            letter-spacing: 0.02em;
        }

        .dtf-mini-btn:hover {
            border-color: #73809b;
            color: #ffffff;
        }

        .dtf-status {
            font-size: 11px;
            color: #8f99ae;
            white-space: nowrap;
        }

        .dtf-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 7px;
            align-items: flex-start;
        }

        .dtf-pill {
            appearance: none;
            border: 1px solid #4f576b;
            background: linear-gradient(180deg, #2a3040 0%, #1f2430 100%);
            color: #c6cedb;
            border-radius: 999px;
            padding: 5px 13px;
            font-size: 12px;
            line-height: 1;
            font-weight: 700;
            cursor: pointer;
            white-space: nowrap;
            transition: background 120ms ease, border-color 120ms ease, color 120ms ease, box-shadow 120ms ease, transform 120ms ease;
        }

        .dtf-pill:hover {
            border-color: #7a859d;
            color: #edf2ff;
            transform: translateY(-1px);
        }

        .dtf-pill.is-selected {
            background: linear-gradient(180deg, #2f83ff 0%, #1f5fd6 100%);
            border-color: #8dc2ff;
            color: #ffffff;
            box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18), 0 0 0 1px rgba(83, 145, 255, 0.18);
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

function getDefaultSelection(categories, keepUnclassified) {
    return categories.filter((category) => category !== UNKNOWN_CATEGORY || keepUnclassified);
}

function createPanel(node) {
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
    help.textContent = "Click categories to keep them";
    root.appendChild(help);

    const toolbar = document.createElement("div");
    toolbar.className = "dtf-toolbar";

    const toolbarActions = document.createElement("div");
    toolbarActions.className = "dtf-toolbar-actions";

    const allButton = document.createElement("button");
    allButton.type = "button";
    allButton.className = "dtf-mini-btn";
    allButton.textContent = "All";
    toolbarActions.appendChild(allButton);

    const noneButton = document.createElement("button");
    noneButton.type = "button";
    noneButton.className = "dtf-mini-btn";
    noneButton.textContent = "None";
    toolbarActions.appendChild(noneButton);

    const status = document.createElement("div");
    status.className = "dtf-status";

    toolbar.appendChild(toolbarActions);
    toolbar.appendChild(status);
    root.appendChild(toolbar);

    const grid = document.createElement("div");
    grid.className = "dtf-grid";
    root.appendChild(grid);

    root.addEventListener("mousedown", (event) => {
        event.stopPropagation();
    });

    document.body.appendChild(root);

    const state = {
        node,
        root,
        toolbar,
        allButton,
        noneButton,
        status,
        grid,
        categories: [],
        selectedCategories: [],
        selectionTouched: false,
        buttons: new Map(),
        panelHeight: MIN_PANEL_HEIGHT,
    };

    allButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        setSelection(node, state, [...state.categories], true);
    });

    noneButton.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        setSelection(node, state, [], true);
    });

    domPanels.set(node.id, state);
    return state;
}

function removePanel(nodeId) {
    const state = domPanels.get(nodeId);
    if (!state) {
        return;
    }

    state.root.remove();
    domPanels.delete(nodeId);
}

function syncSelectedValue(node, state) {
    const backingWidget = getBackingWidget(node, "selected_categories_json");
    const encoded = JSON.stringify(state.selectedCategories);

    if (backingWidget) {
        backingWidget.value = encoded;
    }

    node.properties = node.properties || {};
    node.properties.selected_categories = [...state.selectedCategories];
    node.properties.selected_categories_json = encoded;
    node.properties.__dtfSelectionTouched = Boolean(state.selectionTouched);

    if (Array.isArray(node.widgets_values) && backingWidget) {
        const index = node.widgets?.indexOf(backingWidget);
        if (index >= 0) {
            node.widgets_values[index] = encoded;
        }
    }

    node.setDirtyCanvas(true, true);
}

function updateButtonStyles(state) {
    const selected = new Set(state.selectedCategories);
    for (const [category, button] of state.buttons.entries()) {
        button.classList.toggle("is-selected", selected.has(category));
    }
    state.status.textContent = `${state.selectedCategories.length}/${state.categories.length} selected`;
}

function setSelection(node, state, nextSelection, touched = true) {
    const selected = new Set(nextSelection);
    state.selectedCategories = state.categories.filter((item) => selected.has(item));
    state.selectionTouched = touched;
    updateButtonStyles(state);
    syncSelectedValue(node, state);
}

function toggleCategory(node, state, category) {
    const selected = new Set(state.selectedCategories);
    if (selected.has(category)) {
        selected.delete(category);
    } else {
        selected.add(category);
    }

    setSelection(node, state, [...selected], true);
}

function renderButtons(node, state) {
    const renderKey = JSON.stringify({
        categories: state.categories,
        selected: state.selectedCategories,
    });

    if (state.renderKey === renderKey) {
        updateButtonStyles(state);
        return;
    }

    state.renderKey = renderKey;
    state.grid.replaceChildren();
    state.buttons.clear();

    for (const category of state.categories) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "dtf-pill";
        button.textContent = category;
        button.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            toggleCategory(node, state, category);
        });
        button.addEventListener("mousedown", (event) => {
            event.stopPropagation();
        });
        state.grid.appendChild(button);
        state.buttons.set(category, button);
    }

    updateButtonStyles(state);
}

function addSpacerWidget(node, state) {
    if (node.__dtfSpacerAdded) {
        return;
    }

    const widget = {
        type: "dtf_dom_spacer",
        name: "category_picker",
        value: "",
        options: { serialize: false },
        computeSize(width) {
            const panelWidth = Math.max(width - PANEL_LEFT - PANEL_RIGHT, 180);
            state.root.style.width = `${panelWidth}px`;
            state.panelHeight = Math.max(state.root.offsetHeight || MIN_PANEL_HEIGHT, MIN_PANEL_HEIGHT);
            return [width, state.panelHeight + 8];
        },
        draw() {
            return state.panelHeight + 8;
        },
    };

    node.addCustomWidget(widget);
    node.__dtfSpacerAdded = true;
}

function ensureNodeSize(node, state) {
    const width = Math.max(node.size?.[0] || MIN_NODE_WIDTH, MIN_NODE_WIDTH);
    const panelWidth = Math.max(width - PANEL_LEFT - PANEL_RIGHT, 180);
    state.root.style.width = `${panelWidth}px`;
    state.panelHeight = Math.max(state.root.offsetHeight || MIN_PANEL_HEIGHT, MIN_PANEL_HEIGHT);
    const desiredHeight = PANEL_TOP + state.panelHeight + PANEL_BOTTOM;
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

    const state = createPanel(node);
    addSpacerWidget(node, state);

    const categoriesWidget = getBackingWidget(node, "available_categories_json");
    const selectedWidget = getBackingWidget(node, "selected_categories_json");
    if (categoriesWidget?.value) {
        node.properties = node.properties || {};
        node.properties.available_categories_json = categoriesWidget.value;
    }

    const categories = parseCategoryList(categoriesWidget?.value || node.properties?.available_categories_json);
    const hasWidgetSelection = typeof selectedWidget?.value === "string" && selectedWidget.value.trim().length > 0;
    const hasPropertySelection =
        typeof node.properties?.selected_categories_json === "string" &&
        node.properties.selected_categories_json.trim().length > 0;
    const encodedSelection =
        hasWidgetSelection
            ? selectedWidget.value.trim()
            : hasPropertySelection
              ? node.properties.selected_categories_json.trim()
              : "";

    const previousCategories = JSON.stringify(state.categories);
    const previousSelected = JSON.stringify(state.selectedCategories);
    state.categories = categories;
    if (encodedSelection) {
        state.selectedCategories = parseCategoryList(encodedSelection).filter((category) => categories.includes(category));
        state.selectionTouched = true;
    } else if (Array.isArray(node.properties?.selected_categories)) {
        state.selectedCategories = node.properties.selected_categories.filter((category) => categories.includes(category));
        state.selectionTouched = Boolean(node.properties?.__dtfSelectionTouched);
    } else {
        const keepUnclassified = Boolean(getBackingWidget(node, "keep_unclassified")?.value);
        state.selectedCategories = getDefaultSelection(categories, keepUnclassified);
        state.selectionTouched = false;
    }

    const shouldRestoreDefaultSelection =
        !state.selectedCategories.length &&
        categories.length &&
        !hasWidgetSelection &&
        !hasPropertySelection &&
        !state.selectionTouched;

    if (shouldRestoreDefaultSelection) {
        const keepUnclassified = Boolean(getBackingWidget(node, "keep_unclassified")?.value);
        state.selectedCategories = getDefaultSelection(categories, keepUnclassified);
        state.selectionTouched = false;
    }

    const categoriesChanged = previousCategories !== JSON.stringify(state.categories);
    const selectionChanged = previousSelected !== JSON.stringify(state.selectedCategories);

    renderButtons(node, state);
    if (selectionChanged || categoriesChanged) {
        syncSelectedValue(node, state);
    }
    ensureNodeSize(node, state);
    return state;
}

function updatePanelPosition(state) {
    const { node, root } = state;
    const canvas = app.canvas?.canvas;
    const ds = app.canvas?.ds;
    if (!canvas || !ds || !document.body.contains(canvas)) {
        root.classList.add("is-hidden");
        return;
    }

    if (!document.body.contains(root)) {
        document.body.appendChild(root);
    }

    if (node.flags?.collapsed || node.mode === 4) {
        root.classList.add("is-hidden");
        return;
    }

    ensureNodeSize(node, state);

    const rect = canvas.getBoundingClientRect();
    const scale = ds.scale || 1;
    const left = rect.left + window.scrollX + (node.pos[0] + ds.offset[0] + PANEL_LEFT) * scale;
    const top = rect.top + window.scrollY + (node.pos[1] + ds.offset[1] + PANEL_TOP) * scale;
    const width = Math.max(node.size[0] - PANEL_LEFT - PANEL_RIGHT, 180);

    root.style.width = `${width}px`;
    root.style.transform = `translate(${left}px, ${top}px) scale(${scale})`;
    root.classList.remove("is-hidden");
}

function cleanupPanels() {
    const liveIds = new Set((app.graph?._nodes || []).filter(isTargetNode).map((node) => String(node.id)));
    for (const [nodeId] of domPanels.entries()) {
        if (!liveIds.has(String(nodeId))) {
            removePanel(nodeId);
        }
    }
}

function startLoop() {
    if (loopStarted) {
        return;
    }

    loopStarted = true;
    const tick = () => {
        for (const node of app.graph?._nodes || []) {
            if (!isTargetNode(node)) {
                continue;
            }
            const state = ensureManagedNode(node);
            if (state) {
                updatePanelPosition(state);
            }
        }
        cleanupPanels();
        window.requestAnimationFrame(tick);
    };
    window.requestAnimationFrame(tick);
}

app.registerExtension({
    name: "Danbooru.TagCategoryFilter",
    setup() {
        startLoop();
    },
    nodeCreated(node) {
        ensureManagedNode(node);
        startLoop();
    },
});
