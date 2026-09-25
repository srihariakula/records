const BASE_RESOLUTION = 96; // matches app.services.image_render.DEFAULT_RESOLUTION_ZOOM (96/72)
const ZOOM_STEP = 1.25;
const MIN_RESOLUTION = 24;
const MAX_RESOLUTION = 400;

const state = {
  documentId: null,
  pageCount: 0,
  currentPage: 1,
  currentFile: null,
  resolution: BASE_RESOLUTION,
  zoom: BASE_RESOLUTION / 72, // px-per-point at the current resolution; recomputed in setResolution
  searchQuery: "",
  searchMatches: {}, // { pageNumber: [[x0,y0,x1,y1], ...] } in PDF point space
  lastExtraction: null,
  highlightedField: null, // { page, x, y, width, height } in PDF point space
  currentAnnotations: [], // the current page's annotations, kept in sync with the server after every edit
};

const el = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    let message = resp.statusText;
    try { message = (await resp.json()).message || message; } catch (e) { /* not JSON */ }
    throw new Error(`${resp.status}: ${message}`);
  }
  return resp;
}

async function uploadFile(file) {
  const begin = await api("/Factory/BeginUpload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: file.name }),
  }).then((r) => r.json());

  const form = new FormData();
  form.append("uri", begin.upload_uri);
  form.append("file", file);
  await api("/Factory/UploadDocumentBlob", { method: "POST", body: form });

  return api("/Factory/EndUpload", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ uri: begin.upload_uri }),
  }).then((r) => r.json());
}

function renderThumbnails() {
  const container = el("thumbnails");
  container.innerHTML = "";
  for (let page = 1; page <= state.pageCount; page++) {
    const img = document.createElement("img");
    img.src = `/Page/GetThumbnail?documentId=${state.documentId}&pageNumber=${page}`;
    img.dataset.page = String(page);
    img.addEventListener("click", () => showPage(page));
    container.appendChild(img);
  }
}

function highlightActiveThumbnail() {
  document.querySelectorAll("#thumbnails img").forEach((img) => {
    img.classList.toggle("active", Number(img.dataset.page) === state.currentPage);
  });
}

function setResolution(resolution) {
  // Page/GetImage's `resolution` query param is a strict int server-side --
  // round here so repeated zoom steps (dividing/multiplying by 1.25) never
  // produce a fractional value that the backend would reject with a 422.
  const rounded = Math.round(resolution);
  state.resolution = Math.min(MAX_RESOLUTION, Math.max(MIN_RESOLUTION, rounded));
  state.zoom = state.resolution / 72;
  el("zoom-indicator").textContent = `${Math.round((state.resolution / BASE_RESOLUTION) * 100)}%`;
}

async function showPage(page) {
  state.currentPage = page;
  highlightActiveThumbnail();
  el("page-indicator").textContent = `Page ${page} / ${state.pageCount}`;

  const img = el("page-image");
  await new Promise((resolve) => {
    img.onload = resolve;
    img.src = `/Page/GetImage?documentId=${state.documentId}&pageNumber=${page}&resolution=${state.resolution}`;
  });

  for (const layer of [el("annotation-layer"), el("search-layer"), el("field-highlight-layer")]) {
    layer.style.width = img.naturalWidth + "px";
    layer.style.height = img.naturalHeight + "px";
  }

  renderSearchHighlights();
  renderFieldHighlight();
  await Promise.all([refreshAnnotations(), refreshText()]);
}

async function rerenderCurrentPage() {
  if (state.documentId) await showPage(state.currentPage);
}

async function refreshText() {
  const resp = await api("/Page/GetText", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: state.documentId, page_number: state.currentPage, build_text: true }),
  }).then((r) => r.json());
  el("page-text").textContent = resp.text && resp.text.trim() ? resp.text : "(no embedded text on this page — scanned pages need OCR, which isn't ported)";
}

async function getPageAnnotations() {
  const resp = await api("/Page/GetAnnotations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: state.documentId, page_number: state.currentPage }),
  }).then((r) => r.json());
  return resp.annotations;
}

async function setPageAnnotations(annotations) {
  await api("/Page/SetAnnotations", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: state.documentId, page_number: state.currentPage, annotations }),
  });
}

async function refreshAnnotations() {
  state.currentAnnotations = await getPageAnnotations();
  renderAnnotationBoxes();
}

// Renders state.currentAnnotations as adjustable boxes: drag the body to move,
// drag the bottom-right handle to resize, click the x to delete. Index-based
// identity (position in the per-page array) is fine here since this is a
// single-user local demo and state.currentAnnotations is always the array
// that gets persisted back verbatim -- see setupAnnotationInteractions.
function renderAnnotationBoxes() {
  const layer = el("annotation-layer");
  layer.innerHTML = "";
  state.currentAnnotations.forEach((ann, index) => {
    const box = document.createElement("div");
    box.className = "annotation-box";
    box.dataset.index = String(index);
    box.style.left = ann.x * state.zoom + "px";
    box.style.top = ann.y * state.zoom + "px";
    box.style.width = ann.width * state.zoom + "px";
    box.style.height = ann.height * state.zoom + "px";

    if (ann.text) {
      const label = document.createElement("div");
      label.className = "annotation-label";
      label.textContent = ann.text;
      box.appendChild(label);
    }

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "annotation-delete-btn";
    deleteBtn.textContent = "×";
    deleteBtn.title = "Delete annotation";
    // Stop propagation so the layer's mousedown handler doesn't interpret
    // this as the start of a move-drag.
    deleteBtn.addEventListener("mousedown", (e) => e.stopPropagation());
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      state.currentAnnotations.splice(index, 1);
      await setPageAnnotations(state.currentAnnotations);
      renderAnnotationBoxes();
    });
    box.appendChild(deleteBtn);

    const resizeHandle = document.createElement("div");
    resizeHandle.className = "annotation-resize-handle";
    box.appendChild(resizeHandle);

    layer.appendChild(box);
  });
}

function renderSearchHighlights() {
  const layer = el("search-layer");
  layer.innerHTML = "";
  const rects = state.searchMatches[state.currentPage] || [];
  for (const [x0, y0, x1, y1] of rects) {
    const box = document.createElement("div");
    box.className = "search-highlight";
    box.style.left = x0 * state.zoom + "px";
    box.style.top = y0 * state.zoom + "px";
    box.style.width = (x1 - x0) * state.zoom + "px";
    box.style.height = (y1 - y0) * state.zoom + "px";
    layer.appendChild(box);
  }
}

function renderFieldHighlight() {
  const layer = el("field-highlight-layer");
  layer.innerHTML = "";
  const field = state.highlightedField;
  if (!field || field.page !== state.currentPage) return;

  const box = document.createElement("div");
  box.className = "field-highlight";
  box.style.left = field.x * state.zoom + "px";
  box.style.top = field.y * state.zoom + "px";
  box.style.width = field.width * state.zoom + "px";
  box.style.height = field.height * state.zoom + "px";
  layer.appendChild(box);
}

// Called by the eye icon in the extracted-fields table: jump to the field's
// page (re-rendering also calls renderFieldHighlight via showPage) and scroll
// it into view.
async function viewField(field) {
  state.highlightedField = field;
  await showPage(field.page);

  const wrap = el("image-wrap");
  const targetLeft = field.x * state.zoom - wrap.clientWidth / 2 + (field.width * state.zoom) / 2;
  const targetTop = field.y * state.zoom - wrap.clientHeight / 2 + (field.height * state.zoom) / 2;
  wrap.scrollTo({ left: Math.max(0, targetLeft), top: Math.max(0, targetTop), behavior: "smooth" });
}

// Single delegated mousedown/mousemove/mouseup on the layer covers three
// distinct drags, disambiguated by what the mousedown landed on:
//   - empty layer background -> draw a brand new annotation
//   - an existing box's body/label -> move it
//   - an existing box's resize handle -> resize it
// (The delete button stops propagation on its own mousedown so it never
// starts a move-drag -- see renderAnnotationBoxes.)
function setupAnnotationInteractions() {
  const layer = el("annotation-layer");
  let drawing = null;
  let action = null;

  const minSizePx = 4;

  layer.addEventListener("mousedown", (e) => {
    const rect = layer.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (e.target.classList.contains("annotation-resize-handle")) {
      const index = Number(e.target.closest(".annotation-box").dataset.index);
      action = { type: "resize", index, startX: x, startY: y, orig: { ...state.currentAnnotations[index] } };
      return;
    }

    const existingBox = e.target.closest(".annotation-box");
    if (existingBox) {
      const index = Number(existingBox.dataset.index);
      action = { type: "move", index, startX: x, startY: y, orig: { ...state.currentAnnotations[index] } };
      return;
    }

    drawing = { startX: x, startY: y, box: document.createElement("div") };
    drawing.box.className = "annotation-box";
    layer.appendChild(drawing.box);
  });

  layer.addEventListener("mousemove", (e) => {
    const rect = layer.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (drawing) {
      drawing.box.style.left = Math.min(x, drawing.startX) + "px";
      drawing.box.style.top = Math.min(y, drawing.startY) + "px";
      drawing.box.style.width = Math.abs(x - drawing.startX) + "px";
      drawing.box.style.height = Math.abs(y - drawing.startY) + "px";
      return;
    }

    if (action) {
      const dx = (x - action.startX) / state.zoom;
      const dy = (y - action.startY) / state.zoom;
      const ann = state.currentAnnotations[action.index];
      if (action.type === "move") {
        ann.x = action.orig.x + dx;
        ann.y = action.orig.y + dy;
      } else {
        ann.width = Math.max(minSizePx / state.zoom, action.orig.width + dx);
        ann.height = Math.max(minSizePx / state.zoom, action.orig.height + dy);
      }
      renderAnnotationBoxes(); // live preview; cheap enough for a handful of boxes
    }
  });

  window.addEventListener("mouseup", async () => {
    if (drawing) {
      const box = drawing.box;
      drawing = null;
      const widthPx = parseFloat(box.style.width || "0");
      const heightPx = parseFloat(box.style.height || "0");
      if (widthPx < minSizePx || heightPx < minSizePx) {
        box.remove();
        return;
      }
      showLabelEditor(layer, box, widthPx, heightPx);
      return;
    }

    if (action) {
      action = null;
      await setPageAnnotations(state.currentAnnotations);
    }
  });
}

// A small inline editor instead of window.prompt() -- prompt() is a blocking
// native dialog that's unavailable in some embedded/automated browser contexts
// (it throws there) and is poor UX generally. This attaches a text input plus
// Save/Cancel directly in the annotation layer, positioned under the new box.
function showLabelEditor(layer, box, widthPx, heightPx) {
  const editor = document.createElement("div");
  editor.className = "annotation-editor";
  editor.style.left = parseFloat(box.style.left) + "px";
  editor.style.top = parseFloat(box.style.top) + heightPx + 4 + "px";
  editor.innerHTML = `
    <input type="text" placeholder="Label (optional)" />
    <button data-action="save">Save</button>
    <button data-action="cancel">Cancel</button>
  `;
  layer.appendChild(editor);
  const input = editor.querySelector("input");
  input.focus();

  const cleanup = () => editor.remove();

  editor.querySelector('[data-action="cancel"]').addEventListener("click", () => {
    box.remove();
    cleanup();
  });

  const save = async () => {
    const newAnnotation = {
      page: state.currentPage,
      type: "rect",
      x: parseFloat(box.style.left) / state.zoom,
      y: parseFloat(box.style.top) / state.zoom,
      width: widthPx / state.zoom,
      height: heightPx / state.zoom,
      text: input.value,
    };
    cleanup();
    state.currentAnnotations.push(newAnnotation);
    await setPageAnnotations(state.currentAnnotations);
    renderAnnotationBoxes();
  };

  editor.querySelector('[data-action="save"]').addEventListener("click", save);
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") { box.remove(); cleanup(); }
  });
}

el("clear-annotations-btn").addEventListener("click", async () => {
  state.currentAnnotations = [];
  await setPageAnnotations([]);
  renderAnnotationBoxes();
});

el("prev-page").addEventListener("click", () => {
  if (state.currentPage > 1) showPage(state.currentPage - 1);
});
el("next-page").addEventListener("click", () => {
  if (state.currentPage < state.pageCount) showPage(state.currentPage + 1);
});
el("add-annotation-btn").addEventListener("click", () => {
  alert("Click and drag directly on the page image to draw a rectangle.");
});

el("zoom-in-btn").addEventListener("click", () => {
  setResolution(state.resolution * ZOOM_STEP);
  rerenderCurrentPage();
});
el("zoom-out-btn").addEventListener("click", () => {
  setResolution(state.resolution / ZOOM_STEP);
  rerenderCurrentPage();
});

el("upload-btn").addEventListener("click", async () => {
  const file = el("file-input").files[0];
  if (!file) {
    alert("Choose a file first");
    return;
  }
  el("doc-info").textContent = `Uploading and converting ${file.name} to PDF...`;
  try {
    const doc = await uploadFile(file);
    // The server converts every upload (images, office files, ...) to PDF; if
    // that failed it still caches the file but reports why there are no pages.
    // Keep whatever document was open before rather than showing an empty viewer.
    if (doc.conversion_error || !doc.page_count) {
      el("doc-info").textContent = `Could not open ${file.name}: ${doc.conversion_error || "the document has no pages"}`;
      return;
    }
    state.currentFile = file;
    state.documentId = doc.document_id;
    state.pageCount = doc.page_count;
    state.searchMatches = {};
    state.lastExtraction = null;
    state.highlightedField = null;
    resetConceptSelection();
    setResolution(BASE_RESOLUTION);
    el("doc-info").textContent = `${doc.name || file.name} — ${doc.mime_type}, ${doc.page_count} page(s)`;
    el("download-link").href = `/Factory/DownloadDocument?documentId=${doc.document_id}`;
    el("download-annotated-link").href = `/Factory/DownloadAnnotatedDocument?documentId=${doc.document_id}`;
    el("download-ann-xml-link").href = `/Factory/DownloadAnnotationsXml?documentId=${doc.document_id}`;
    el("search-results").innerHTML = "";
    el("fields-table").hidden = true;
    el("fields-empty").textContent = "";
    el("download-fields-btn").disabled = true;
    el("viewer").hidden = false;
    renderThumbnails();
    await showPage(1);
  } catch (err) {
    el("doc-info").textContent = `Upload failed: ${err.message}`;
  }
});

// Shared result handling: stores the matches, renders the per-page results
// list, and highlights the current page.
function applyMatchResponse(resp) {
  const resultsEl = el("search-results");
  state.searchMatches = {};
  for (const [page, rects] of Object.entries(resp.matches)) {
    state.searchMatches[Number(page)] = rects;
  }
  resultsEl.innerHTML = "";
  if (resp.total_matches === 0) {
    resultsEl.textContent = "No matches.";
  } else {
    const pages = Object.keys(state.searchMatches).map(Number).sort((a, b) => a - b);
    for (const page of pages) {
      const count = state.searchMatches[page].length;
      const row = document.createElement("div");
      row.textContent = `Page ${page}: ${count} match${count === 1 ? "" : "es"}`;
      row.addEventListener("click", () => showPage(page));
      resultsEl.appendChild(row);
    }
  }
  renderSearchHighlights();
}

function selectedConceptIds() {
  return Array.from(document.querySelectorAll("#concept-dropdown-panel input[type=checkbox]:checked")).map(
    (cb) => cb.value
  );
}

function updateConceptDropdownLabel() {
  const count = selectedConceptIds().length;
  el("concept-dropdown-btn").textContent = count === 0 ? "Select concepts ▾" : `${count} concept${count === 1 ? "" : "s"} selected ▾`;
}

function resetConceptSelection() {
  document.querySelectorAll("#concept-dropdown-panel input[type=checkbox]").forEach((cb) => (cb.checked = false));
  updateConceptDropdownLabel();
}

// Runs a single AND search combining the free-text query (if any) with every
// checked concept in the dropdown -- Factory/SearchMultiCriteria only
// returns pages where ALL selected criteria matched (see that endpoint).
el("search-btn").addEventListener("click", async () => {
  const query = el("search-input").value.trim();
  const conceptIds = selectedConceptIds();
  if (!state.documentId || (!query && conceptIds.length === 0)) return;

  const resultsEl = el("search-results");
  resultsEl.textContent = "Searching...";
  try {
    const resp = await api("/Factory/SearchMultiCriteria", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        document_id: state.documentId,
        query: query || null,
        case_sensitive: el("search-case-sensitive").checked,
        whole_word: el("search-whole-word").checked,
        use_regex: el("search-regex").checked,
        use_ner: el("search-ner").checked,
        concept_ids: conceptIds,
      }),
    }).then((r) => r.json());
    applyMatchResponse(resp);
  } catch (err) {
    resultsEl.textContent = `Error: ${err.message}`;
  }
});
el("search-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter") el("search-btn").click();
});

// NER mode sends the search text to GLiNER2 as an entity type rather than
// matching it literally, so the literal-match options don't apply.
const LITERAL_SEARCH_OPTIONS = ["search-case-sensitive", "search-whole-word", "search-regex"];
el("search-ner").addEventListener("change", () => {
  const ner = el("search-ner").checked;
  for (const id of LITERAL_SEARCH_OPTIONS) el(id).disabled = ner;
  el("search-input").placeholder = ner ? "Entity type, e.g. medication..." : "Search this document...";
});

// Concept dropdown: Factory/ListConcepts is the source of truth for id+label
// (app.services.concepts_registry on the backend), so this markup never
// needs to duplicate that list.
async function loadConcepts() {
  let info;
  try {
    info = await api("/Factory/ListConcepts").then((r) => r.json());
  } catch (err) {
    return; // search bar still works without the concept checklist
  }

  const regexContainer = el("regex-concept-checks");
  regexContainer.innerHTML = "";
  for (const concept of info.regex_concepts) {
    regexContainer.appendChild(buildConceptCheckbox(concept));
  }

  const nerCheckbox = el("search-ner");
  nerCheckbox.disabled = !info.ner_available;
  if (!info.ner_available && nerCheckbox.checked) {
    nerCheckbox.checked = false;
    nerCheckbox.dispatchEvent(new Event("change"));
  }
  el("ner-unavailable-hint").hidden = info.ner_available;
}

function buildConceptCheckbox(concept) {
  const label = document.createElement("label");
  const input = document.createElement("input");
  input.type = "checkbox";
  input.value = concept.id;
  input.addEventListener("change", updateConceptDropdownLabel);
  label.appendChild(input);
  label.appendChild(document.createTextNode(" " + concept.label));
  return label;
}

function setupConceptDropdown() {
  const dropdown = el("concept-dropdown");
  const panel = el("concept-dropdown-panel");
  el("concept-dropdown-btn").addEventListener("click", () => {
    panel.hidden = !panel.hidden;
  });
  document.addEventListener("click", (e) => {
    if (!panel.hidden && !dropdown.contains(e.target)) panel.hidden = true;
  });
}

el("extract-fields-btn").addEventListener("click", async () => {
  if (!state.documentId) return;
  const table = el("fields-table");
  const tbody = table.querySelector("tbody");
  const emptyMsg = el("fields-empty");
  emptyMsg.textContent = "Extracting...";
  try {
    const result = await api(`/Factory/ExtractAnnotatedFields?documentId=${state.documentId}`).then((r) => r.json());
    state.lastExtraction = result;
    tbody.innerHTML = "";
    if (result.fields.length === 0) {
      table.hidden = true;
      emptyMsg.textContent = "No labeled annotations to extract yet — draw one with a label first.";
      el("download-fields-btn").disabled = true;
      return;
    }
    for (const field of result.fields) {
      tbody.appendChild(buildFieldRow(field));
    }
    table.hidden = false;
    emptyMsg.textContent = "";
    el("download-fields-btn").disabled = false;
  } catch (err) {
    emptyMsg.textContent = `Error: ${err.message}`;
  }
});

el("download-fields-btn").addEventListener("click", () => {
  if (!state.lastExtraction) return;
  const blob = new Blob([JSON.stringify(state.lastExtraction, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${state.documentId}_fields.json`;
  a.click();
  URL.revokeObjectURL(url);
});

// Builds one editable row for the extracted-fields table: Label and Value are
// plain <input>s (safe from HTML injection since we set .value, not innerHTML);
// the save button stays disabled until either differs from the last-saved
// field, and commits both via Factory/UpdateAnnotatedField, identified by the
// field's (page, index) -- the same position-in-page-array identity already
// used for move/resize/delete on the page itself.
function buildFieldRow(field) {
  const row = document.createElement("tr");

  const pageCell = document.createElement("td");
  pageCell.textContent = field.page;

  const labelInput = document.createElement("input");
  labelInput.type = "text";
  labelInput.value = field.label;
  const labelCell = document.createElement("td");
  labelCell.appendChild(labelInput);

  const valueInput = document.createElement("input");
  valueInput.type = "text";
  valueInput.value = field.value;
  const valueCell = document.createElement("td");
  valueCell.appendChild(valueInput);

  const viewBtn = document.createElement("button");
  viewBtn.textContent = "\u{1F441}\u{FE0F}";
  viewBtn.title = "Highlight on page";
  viewBtn.addEventListener("click", () => viewField(field));

  const saveBtn = document.createElement("button");
  saveBtn.className = "save-field-btn";
  saveBtn.textContent = "\u{1F4BE}";
  saveBtn.title = "Save changes";
  saveBtn.disabled = true;

  const markDirty = () => {
    labelInput.classList.toggle("dirty", labelInput.value !== field.label);
    valueInput.classList.toggle("dirty", valueInput.value !== field.value);
    saveBtn.disabled = labelInput.value === field.label && valueInput.value === field.value;
  };
  labelInput.addEventListener("input", markDirty);
  valueInput.addEventListener("input", markDirty);

  saveBtn.addEventListener("click", async () => {
    saveBtn.disabled = true;
    try {
      await api("/Factory/UpdateAnnotatedField", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: state.documentId,
          page: field.page,
          index: field.index,
          label: labelInput.value,
          value: valueInput.value,
        }),
      });
      field.label = labelInput.value;
      field.value = valueInput.value;
      labelInput.classList.remove("dirty");
      valueInput.classList.remove("dirty");
      if (state.lastExtraction) {
        state.lastExtraction.key_values = {};
        for (const f of state.lastExtraction.fields) state.lastExtraction.key_values[f.label] = f.value;
      }
      if (field.page === state.currentPage) await refreshAnnotations();
    } catch (err) {
      alert(`Save failed: ${err.message}`);
      saveBtn.disabled = false;
    }
  });

  const actionsCell = document.createElement("td");
  actionsCell.className = "field-actions";
  actionsCell.appendChild(viewBtn);
  actionsCell.appendChild(saveBtn);

  row.append(pageCell, labelCell, valueCell, actionsCell);
  return row;
}

el("detect-qr-btn").addEventListener("click", async () => {
  if (!state.currentFile) return;
  el("qr-result").textContent = "Detecting...";
  const form = new FormData();
  form.append("file", state.currentFile);
  try {
    const resp = await api("/qrcode/detect", { method: "POST", body: form }).then((r) => r.json());
    const entries = Object.entries(resp.pagewise_qr_codes);
    el("qr-result").textContent = entries.length
      ? entries.map(([page, values]) => `Page ${page}: ${values.join(", ")}`).join("\n")
      : "No QR codes found.";
  } catch (err) {
    el("qr-result").textContent = `Error: ${err.message}`;
  }
});

el("qr-generate-btn").addEventListener("click", async () => {
  const text = el("qr-generate-input").value.trim();
  if (!text) return;
  const resp = await api("/qrcode/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qrcode: text }),
  });
  const blob = await resp.blob();
  el("qr-generate-result").src = URL.createObjectURL(blob);
});

// Show/hide toggles for Page text, QR codes, Generate QR code, and the page
// navigator (thumbnail strip). Sections use a shared [data-target] pattern;
// the thumbnail strip is handled separately since hiding it also needs to
// collapse its grid column (see main#viewer.thumbnails-hidden in style.css),
// not just hide the element.
function setupCollapsibleSections() {
  document.querySelectorAll(".toggle-btn[data-target]").forEach((btn) => {
    const target = el(btn.dataset.target);
    btn.addEventListener("click", () => {
      const nowHidden = !target.hasAttribute("hidden");
      target.hidden = nowHidden;
      btn.classList.toggle("collapsed", nowHidden);
      btn.title = nowHidden ? "Show" : "Hide";
    });
  });

  const toggleThumbnailsBtn = el("toggle-thumbnails-btn");
  toggleThumbnailsBtn.addEventListener("click", () => {
    const hidden = el("viewer").classList.toggle("thumbnails-hidden");
    toggleThumbnailsBtn.classList.toggle("collapsed", hidden);
    toggleThumbnailsBtn.title = hidden ? "Show page navigator" : "Hide page navigator";
  });
}

setupAnnotationInteractions();
setupCollapsibleSections();
setupConceptDropdown();
loadConcepts();
