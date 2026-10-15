/**
 * Palm Leaf Manuscript Reader - Modern Pipeline Client
 * Connects frontend manuscript upload with POST /api/upload-and-process and POST /api/export
 * Handles validation, preview, line transcription editing, and Tamil Unicode exports.
 */

document.addEventListener("DOMContentLoaded", () => {
  // DOM Elements
  const fileInput = document.getElementById("file-upload");
  const form = document.getElementById("form");
  const dragLabel = document.getElementById("drag-drop-label");
  const statusAlert = document.getElementById("status-alert");
  const loadingContainer = document.getElementById("loading-container");
  const workspaceContainer = document.getElementById("workspace-container");
  const previewImage = document.getElementById("preview-image");
  const previewFilename = document.getElementById("preview-filename");
  const previewMeta = document.getElementById("preview-meta");
  const linesContainer = document.getElementById("lines-container");
  const statLineCount = document.getElementById("stat-line-count");
  const statAvgConf = document.getElementById("stat-avg-conf");
  const statLatency = document.getElementById("stat-latency");
  const btnExportTxt = document.getElementById("btn-export-txt");
  const btnExportJson = document.getElementById("btn-export-json");
  const btnExportCsv = document.getElementById("btn-export-csv");
  const btnExportTei = document.getElementById("btn-export-tei");
  const btnSaveDb = document.getElementById("btn-save-db");
  const btnModeOrig = document.getElementById("btn-mode-orig");
  const btnModeEnh = document.getElementById("btn-mode-enh");
  const btnCopyText = document.getElementById("btn-copy-text");

  // State
  let currentFile = null;
  let currentFilename = "manuscript.png";
  let currentImageUrl = null;
  let currentEnhancedImageUrl = null;
  let currentManuscriptId = null;
  let pipelineResults = null;
  let userHasEdited = false;

  const SUPPORTED_EXTS = [".png", ".jpg", ".jpeg", ".webp"];
  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

  // -------------------------------------------------------------
  // Alert Helpers
  // -------------------------------------------------------------
  function showAlert(message, type = "error") {
    if (!statusAlert) return;
    statusAlert.className = `status-alert alert-${type}`;
    statusAlert.innerHTML = `
      <div class="alert-content">
        <span class="alert-icon">${type === "error" ? "⚠️" : type === "warning" ? "⚡" : "✓"}</span>
        <span class="alert-text">${escapeHtml(message)}</span>
      </div>
      <button class="alert-close" onclick="this.parentElement.style.display='none'">&times;</button>
    `;
    statusAlert.style.display = "flex";
  }

  function clearAlert() {
    if (!statusAlert) return;
    statusAlert.style.display = "none";
    statusAlert.innerHTML = "";
  }

  function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // -------------------------------------------------------------
  // Validation
  // -------------------------------------------------------------
  function validateFile(file) {
    if (!file) {
      return "Please select a palm-leaf manuscript image file.";
    }

    const name = file.name || "";
    const lastDot = name.lastIndexOf(".");
    const ext = lastDot !== -1 ? name.slice(lastDot).toLowerCase() : "";

    if (!SUPPORTED_EXTS.includes(ext)) {
      return `Unsupported file format '${ext || "unknown"}'. Please upload a PNG, JPG, JPEG, or WEBP image.`;
    }

    if (file.size > MAX_FILE_SIZE) {
      const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
      return `File size (${sizeMb} MB) exceeds maximum permitted limit of 50 MB.`;
    }

    if (file.size === 0) {
      return "Uploaded file is empty (0 bytes). Please select a valid manuscript image.";
    }

    return null;
  }

  // -------------------------------------------------------------
  // Loading State
  // -------------------------------------------------------------
  function setLoading(isLoading, message = "Analyzing manuscript...") {
    if (loadingContainer) {
      loadingContainer.style.display = isLoading ? "flex" : "none";
      const loadingText = document.getElementById("loading-text");
      if (loadingText) loadingText.textContent = message;
    }
    if (fileInput) fileInput.disabled = isLoading;
    if (btnExportTxt) btnExportTxt.disabled = isLoading;
    if (btnExportJson) btnExportJson.disabled = isLoading;
    if (btnCopyText) btnCopyText.disabled = isLoading;
  }

  // -------------------------------------------------------------
  // Process Upload
  // -------------------------------------------------------------
  async function handleFileUpload(file) {
    if (userHasEdited) {
      const confirmDiscard = window.confirm("You have edited text in the current transcription. Do you want to discard your edits and load a new manuscript image?");
      if (!confirmDiscard) return;
    }
    userHasEdited = false;
    clearAlert();

    const valError = validateFile(file);
    if (valError) {
      showAlert(valError, "error");
      return;
    }

    currentFile = file;
    currentFilename = file.name;

    // Display client preview immediately
    if (currentImageUrl) {
      URL.revokeObjectURL(currentImageUrl);
    }
    currentImageUrl = URL.createObjectURL(file);
    if (previewImage) {
      previewImage.src = currentImageUrl;
    }
    if (previewFilename) {
      previewFilename.textContent = file.name;
    }
    if (previewMeta) {
      const sizeKb = (file.size / 1024).toFixed(1);
      previewMeta.textContent = `${sizeKb} KB • Initializing OCR...`;
    }

    // Ensure workspace is visible
    if (workspaceContainer) {
      workspaceContainer.style.display = "flex";
    }

    // Clear previous lines while loading
    if (linesContainer) {
      linesContainer.innerHTML = '<div class="lines-placeholder">Running line segmentation & Tamil OCR inference...</div>';
    }

    setLoading(true, "Detecting text lines and recognizing Tamil characters...");

    // Send FormData to /api/upload-and-process
    const formData = new FormData();
    formData.append("image", file);

    try {
      const response = await fetch("/api/upload-and-process", {
        method: "POST",
        body: formData
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        const errorMsg = data.error || `Processing failed (HTTP ${response.status}).`;
        showAlert(errorMsg, "error");
        if (linesContainer) {
          linesContainer.innerHTML = `<div class="lines-error">⚠️ ${escapeHtml(errorMsg)}</div>`;
        }
        return;
      }

      pipelineResults = data;
      currentManuscriptId = data.manuscript_id || null;
      if (data.enhanced_image) {
        currentEnhancedImageUrl = data.enhanced_image;
      }
      renderPipelineResults(data);

      if (data.warnings && data.warnings.length > 0) {
        showAlert(`Notice: ${data.warnings.join(", ")}`, "warning");
      }

    } catch (err) {
      console.error("Pipeline network error:", err);
      showAlert(`Network or server error: ${err.message}. Ensure backend is running.`, "error");
      if (linesContainer) {
        linesContainer.innerHTML = `<div class="lines-error">⚠️ Connection error: ${escapeHtml(err.message)}</div>`;
      }
    } finally {
      setLoading(false);
    }
  }

  // -------------------------------------------------------------
  // Render OCR Lines & Metrics
  // -------------------------------------------------------------
  function renderPipelineResults(data) {
    const lines = data.lines || [];
    const meta = data.metadata || {};

    // Update metadata header
    if (previewMeta) {
      const w = meta.image_width || "?";
      const h = meta.image_height || "?";
      const segTime = meta.segmentation_time_ms ? `${meta.segmentation_time_ms}ms` : "-";
      previewMeta.textContent = `${w} × ${h} px • Seg: ${segTime}`;
    }

    if (statLineCount) {
      statLineCount.textContent = `${lines.length} Line${lines.length === 1 ? "" : "s"}`;
    }

    if (statLatency) {
      const totalMs = meta.total_processing_time_ms ? Math.round(meta.total_processing_time_ms) : "-";
      statLatency.textContent = `${totalMs} ms`;
    }

    // Compute average confidence
    if (statAvgConf) {
      const confScores = lines
        .map(l => l.confidence)
        .filter(c => typeof c === "number" && !isNaN(c));
      if (confScores.length > 0) {
        const avg = confScores.reduce((a, b) => a + b, 0) / confScores.length;
        const avgPct = (avg * 100).toFixed(1);
        statAvgConf.textContent = `${avgPct}% Avg Conf`;
      } else {
        statAvgConf.textContent = "N/A";
      }
    }

    // Render Line Cards
    if (!linesContainer) return;

    if (lines.length === 0) {
      linesContainer.innerHTML = `
        <div class="empty-lines-card">
          <p>No manuscript text lines detected.</p>
          <p class="empty-subtext">Check the image contrast or upload another palm-leaf image.</p>
        </div>
      `;
      return;
    }

    linesContainer.innerHTML = "";

    lines.forEach((line) => {
      const card = document.createElement("div");
      card.className = "line-card";
      card.id = `line-card-${line.line_index}`;

      // Confidence styling
      let confBadgeHtml = '<span class="conf-badge conf-none">N/A</span>';
      if (line.confidence !== null && line.confidence !== undefined) {
        const confNum = parseFloat(line.confidence);
        if (!isNaN(confNum)) {
          const pct = (confNum * 100).toFixed(1);
          let confClass = "conf-high";
          let reviewNote = "";
          if (confNum < 0.45) {
            confClass = "conf-low";
            reviewNote = ' <span class="review-tag" title="Character confidence is low: manual review recommended">⚠️ Review Needed</span>';
          } else if (confNum < 0.70) {
            confClass = "conf-med";
            reviewNote = ' <span class="review-tag-med" title="Moderate confidence: verify against original scan">⚠️ Moderate</span>';
          }
          confBadgeHtml = `<span class="conf-badge ${confClass}">${pct}% Conf</span>${reviewNote}`;
        }
      }

      // Margin tag
      const marginHtml = line.is_margin
        ? '<span class="margin-badge">Margin Heading</span>'
        : "";

      // Latency tag
      const latencyHtml = line.latency_ms
        ? `<span class="latency-badge">${Math.round(line.latency_ms)}ms</span>`
        : "";

      // Bounding box tag
      const bboxStr = Array.isArray(line.bbox) ? `[${line.bbox.join(", ")}]` : "";
      const bboxHtml = bboxStr ? `<span class="bbox-badge" title="Bounding Box (x, y, w, h)">${bboxStr}</span>` : "";

      // Line Crop preview
      const cropHtml = line.crop_base64
        ? `<div class="line-crop-preview" style="margin-bottom: 8px; border-radius: 4px; overflow: hidden; border: 1px solid #d5dbdb; background: #2c3e50;">
             <img src="${line.crop_base64}" alt="Line ${line.line_index} crop" style="width: 100%; max-height: 70px; object-fit: contain; display: block;" />
           </div>`
        : "";

      // Raw OCR Reading
      const rawText = line.raw_text || line.raw_ocr_text || line.text || "";
      const rawOcrHtml = rawText
        ? `<div style="font-size: 13px; color: #7f8c8d; margin-bottom: 5px;">
             <strong>Raw Optical Reading:</strong> <span style="font-family: 'Noto Sans Tamil', monospace; color: #2c3e50; font-size: 14px;">${escapeHtml(rawText)}</span>
           </div>`
        : "";

      // Epigraphical Correction Suggestion
      const suggText = line.proposed_correction || line.corrected_text || "";
      const hasSuggestion = Boolean(suggText && suggText !== rawText);
      const suggestionHtml = hasSuggestion
        ? `<div style="font-size: 13px; color: #0c7d81; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; background: #e8f6f3; padding: 4px 8px; border-radius: 4px;">
             <span><strong>💡 Epigraphical Suggestion:</strong> <span style="font-family: 'Noto Sans Tamil', sans-serif;">${escapeHtml(suggText)}</span></span>
             <button type="button" class="btn-use-sugg" style="padding: 2px 8px; font-size: 11px; cursor: pointer; border-radius: 4px; background: #0c7d81; color: #fff; border: none; font-weight: 600;">Use Suggestion</button>
           </div>`
        : "";

      card.innerHTML = `
        <div class="line-card-header">
          <div class="line-header-left">
            <span class="line-index-badge">Line ${line.line_index || line.line_number}</span>
            ${marginHtml}
          </div>
          <div class="line-header-right">
            ${bboxHtml}
            ${latencyHtml}
            ${confBadgeHtml}
          </div>
        </div>
        <div class="line-card-body">
          ${cropHtml}
          ${rawOcrHtml}
          ${suggestionHtml}
          <div style="font-size: 12px; font-weight: 600; color: #753835; margin-bottom: 4px;">Editable Transcription:</div>
          <textarea
            class="line-text-input"
            data-line-index="${line.line_index || line.line_number}"
            data-line-id="${line.id || ''}"
            rows="2"
            spellcheck="false"
            placeholder="Edit recognized Tamil text..."
          >${escapeHtml(line.text || line.final_reviewed_text || line.corrected_text || "")}</textarea>
        </div>
      `;

      // Track user edits
      const textarea = card.querySelector(".line-text-input");
      if (textarea) {
        textarea.addEventListener("input", () => {
          userHasEdited = true;
        });
      }

      // Handle Use Suggestion button
      const useSuggBtn = card.querySelector(".btn-use-sugg");
      if (useSuggBtn) {
        useSuggBtn.addEventListener("click", () => {
          if (textarea && suggText) {
            textarea.value = suggText;
            userHasEdited = true;
          }
        });
      }

      linesContainer.appendChild(card);
    });
  }

  // -------------------------------------------------------------
  // Export Handling
  // -------------------------------------------------------------
  async function exportTranscription(format) {
    clearAlert();

    const textInputs = document.querySelectorAll(".line-text-input");
    if (!textInputs || textInputs.length === 0) {
      showAlert("No transcription lines available to export. Please process a manuscript first.", "warning");
      return;
    }

    // Collect edited lines in strict line_index order
    const editedLines = [];
    textInputs.forEach((input) => {
      const idx = parseInt(input.getAttribute("data-line-index"), 10) || (editedLines.length + 1);
      editedLines.push({
        line_index: idx,
        text: input.value
      });
    });

    const payload = {
      filename: currentFilename,
      format: format,
      lines: editedLines,
      metadata: pipelineResults ? pipelineResults.metadata : {}
    };

    setLoading(true, `Exporting as ${format.toUpperCase()}...`);

    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.error || `Export failed with status ${response.status}`);
      }

      // Determine downloaded filename from header or fallback
      let downloadFilename = `${currentFilename.replace(/\.[^/.]+$/, "")}_transcription.${format}`;
      const disposition = response.headers.get("Content-Disposition");
      if (disposition && disposition.includes("filename=")) {
        const match = disposition.match(/filename="?([^";]+)"?/);
        if (match && match[1]) {
          downloadFilename = match[1];
        }
      }

      // Create download blob
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const downloadLink = document.createElement("a");
      downloadLink.href = blobUrl;
      downloadLink.download = downloadFilename;
      document.body.appendChild(downloadLink);
      downloadLink.click();
      document.body.removeChild(downloadLink);
      URL.revokeObjectURL(blobUrl);

      showAlert(`Exported successfully: ${downloadFilename}`, "success");
    } catch (err) {
      console.error("Export error:", err);
      showAlert(`Export failed: ${err.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  // -------------------------------------------------------------
  // Copy to Clipboard
  // -------------------------------------------------------------
  function copyTextToClipboard() {
    const textInputs = document.querySelectorAll(".line-text-input");
    if (!textInputs || textInputs.length === 0) {
      showAlert("No transcription available to copy.", "warning");
      return;
    }

    const lines = [];
    textInputs.forEach(input => lines.push(input.value));
    const fullText = lines.join("\n");

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(fullText).then(() => {
        if (btnCopyText) {
          const original = btnCopyText.innerHTML;
          btnCopyText.innerHTML = "✓ Copied!";
          setTimeout(() => { btnCopyText.innerHTML = original; }, 2000);
        }
      }).catch(err => {
        fallbackCopyText(fullText);
      });
    } else {
      fallbackCopyText(fullText);
    }
  }

  function fallbackCopyText(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand("copy");
      if (btnCopyText) {
        const original = btnCopyText.innerHTML;
        btnCopyText.innerHTML = "✓ Copied!";
        setTimeout(() => { btnCopyText.innerHTML = original; }, 2000);
      }
    } catch (e) {
      showAlert("Could not copy text to clipboard.", "warning");
    }
    document.body.removeChild(ta);
  }

  // -------------------------------------------------------------
  // Event Listeners
  // -------------------------------------------------------------

  // File input change
  if (fileInput) {
    fileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        handleFileUpload(e.target.files[0]);
      }
    });
  }

  // Form submit prevention (intercept legacy form)
  if (form) {
    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (fileInput && fileInput.files && fileInput.files[0]) {
        handleFileUpload(fileInput.files[0]);
      }
    });
  }

  // Drag and Drop
  if (dragLabel) {
    ["dragenter", "dragover"].forEach(eventName => {
      dragLabel.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragLabel.classList.add("dragover");
      });
    });

    ["dragleave", "dragend"].forEach(eventName => {
      dragLabel.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dragLabel.classList.remove("dragover");
      });
    });

    dragLabel.addEventListener("drop", (e) => {
      e.preventDefault();
      e.stopPropagation();
      dragLabel.classList.remove("dragover");

      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        const droppedFile = e.dataTransfer.files[0];
        handleFileUpload(droppedFile);
      }
    });
  }

  // Save to Database
  async function saveTranscriptionToDatabase() {
    clearAlert();
    const textInputs = document.querySelectorAll(".line-text-input");
    if (!textInputs || textInputs.length === 0) {
      showAlert("No transcription lines available to save.", "warning");
      return;
    }

    if (!currentManuscriptId) {
      showAlert("No active manuscript ID. Please upload a manuscript first.", "warning");
      return;
    }

    const linesToSave = [];
    textInputs.forEach((input) => {
      const idx = parseInt(input.getAttribute("data-line-index"), 10) || 1;
      const lineId = input.getAttribute("data-line-id") || null;
      linesToSave.push({
        id: lineId,
        line_number: idx,
        line_index: idx,
        text: input.value
      });
    });

    setLoading(true, "Saving changes to database...");

    try {
      const resp = await fetch(`/api/v1/manuscripts/${currentManuscriptId}/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lines: linesToSave })
      });
      const resJson = await resp.json();
      if (!resp.ok || !resJson.success) {
        throw new Error(resJson.error || "Save failed.");
      }
      userHasEdited = false;
      showAlert(`✓ Successfully saved ${resJson.updated || linesToSave.length} lines to database! Edits will persist across reloads and server restarts.`, "success");
    } catch (e) {
      showAlert(`Save failed: ${e.message}`, "error");
    } finally {
      setLoading(false);
    }
  }

  if (btnSaveDb) {
    btnSaveDb.addEventListener("click", saveTranscriptionToDatabase);
  }

  // Export buttons
  if (btnExportTxt) {
    btnExportTxt.addEventListener("click", () => exportTranscription("txt"));
  }

  if (btnExportCsv) {
    btnExportCsv.addEventListener("click", () => exportTranscription("csv"));
  }

  if (btnExportJson) {
    btnExportJson.addEventListener("click", () => exportTranscription("json"));
  }

  if (btnExportTei) {
    btnExportTei.addEventListener("click", () => exportTranscription("tei-xml"));
  }

  if (btnCopyText) {
    btnCopyText.addEventListener("click", copyTextToClipboard);
  }

  // Image mode toggles
  if (btnModeOrig) {
    btnModeOrig.addEventListener("click", () => {
      if (currentImageUrl && previewImage) {
        previewImage.src = currentImageUrl;
        btnModeOrig.style.background = "#e8f6f3";
        btnModeOrig.style.color = "#0c7d81";
        btnModeOrig.style.borderColor = "#0c7d81";
        if (btnModeEnh) {
          btnModeEnh.style.background = "#fdfefe";
          btnModeEnh.style.color = "#7f8c8d";
          btnModeEnh.style.borderColor = "#bdc3c7";
        }
      }
    });
  }

  if (btnModeEnh) {
    btnModeEnh.addEventListener("click", () => {
      if (currentEnhancedImageUrl && previewImage) {
        previewImage.src = currentEnhancedImageUrl;
        btnModeEnh.style.background = "#e8f6f3";
        btnModeEnh.style.color = "#0c7d81";
        btnModeEnh.style.borderColor = "#0c7d81";
        if (btnModeOrig) {
          btnModeOrig.style.background = "#fdfefe";
          btnModeOrig.style.color = "#7f8c8d";
          btnModeOrig.style.borderColor = "#bdc3c7";
        }
      } else {
        showAlert("Enhanced scan image is generating or not available for this scan.", "warning");
      }
    });
  }

  // Preloaded manuscript from SQLite check
  const preloadedScript = document.getElementById("preloaded-data");
  if (preloadedScript) {
    try {
      const preloaded = JSON.parse(preloadedScript.textContent);
      if (preloaded && preloaded.manuscript_id) {
        currentManuscriptId = preloaded.manuscript_id;
        currentFilename = preloaded.title || "manuscript.png";
        if (previewFilename) previewFilename.textContent = currentFilename;
        if (workspaceContainer) workspaceContainer.style.display = "flex";
        if (preloaded.original_image_path && previewImage) {
          previewImage.src = preloaded.original_image_path;
          currentImageUrl = preloaded.original_image_path;
        }
        if (preloaded.enhanced_image_path) {
          currentEnhancedImageUrl = preloaded.enhanced_image_path;
        }
        renderPipelineResults({
          lines: (preloaded.lines || []).map(l => ({
            line_index: l.line_number,
            id: l.id,
            bbox: l.bbox,
            text: l.final_reviewed_text || l.corrected_text || l.raw_ocr_text,
            raw_text: l.raw_ocr_text,
            proposed_correction: l.corrected_text,
            confidence: l.confidence
          })),
          metadata: {
            line_count: (preloaded.lines || []).length,
            image_width: "?",
            image_height: "?"
          }
        });
      }
    } catch (e) {
      console.warn("Could not parse preloaded manuscript:", e);
    }
  }

  // Reset button
  const btnReset = document.getElementById("btn-reset");
  if (btnReset) {
    btnReset.addEventListener("click", () => {
      if (fileInput) fileInput.value = "";
      if (workspaceContainer) workspaceContainer.style.display = "none";
      if (previewImage) previewImage.src = "";
      if (previewFilename) previewFilename.textContent = "Uploaded Image";
      if (previewMeta) previewMeta.textContent = "";
      if (linesContainer) linesContainer.innerHTML = "";
      currentManuscriptId = null;
      currentImageUrl = null;
      currentEnhancedImageUrl = null;
      pipelineResults = null;
      clearAlert();
    });
  }
});

// Fullscreen Modal functions (global for onclick attributes)
window.showImage = function() {
  const modal = document.getElementById("image");
  const modalImg = document.getElementById("image_output_view");
  const closeBtn = document.getElementById("close");
  const previewImg = document.getElementById("preview-image");

  if (modal && modalImg && previewImg && previewImg.src) {
    modalImg.src = previewImg.src;
    modal.style.display = "block";
    if (closeBtn) closeBtn.style.display = "block";
  }
};

window.closed = function() {
  const modal = document.getElementById("image");
  const closeBtn = document.getElementById("close");
  if (modal) modal.style.display = "none";
  if (closeBtn) closeBtn.style.display = "none";
};
