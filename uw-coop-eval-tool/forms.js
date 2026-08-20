(() => {
    const pageType = document.body.dataset.formType;
    if (!pageType) return;

    const THEME_KEY = "uw_theme";
    const html = document.documentElement;
    const themeBtn = document.getElementById("themeToggle");
    const toast = document.getElementById("toast");
    const importFileInput = document.getElementById("importFileInput");

    let toastTimer;

    function applyTheme(theme) {
        html.dataset.theme = theme;
        if (themeBtn) {
            themeBtn.textContent = theme === "dark" ? "☀️" : "🌙";
        }
        localStorage.setItem(THEME_KEY, theme);
    }

    function showToast(message) {
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("show");
        clearTimeout(toastTimer);
        toastTimer = setTimeout(() => toast.classList.remove("show"), 2800);
    }

    function sanitizedFileSegment(value, fallback) {
        return (
            (value || fallback)
                .toLowerCase()
                .trim()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-+|-+$/g, "") || fallback
        );
    }

    function datePrefix() {
        return new Date().toISOString().slice(0, 10);
    }

    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = filename;
        anchor.click();
        URL.revokeObjectURL(url);
    }

    function isJsonFile(file) {
        return (
            file &&
            (file.type === "application/json" ||
                file.name.toLowerCase().endsWith(".json"))
        );
    }

    function eventHasFiles(event) {
        return [...(event.dataTransfer?.types || [])].includes("Files");
    }

    function setupJsonImport(importData) {
        function importFile(file) {
            if (!file) return;

            if (!isJsonFile(file)) {
                showToast("Please import a JSON file.");
                return;
            }

            const reader = new FileReader();
            reader.onload = (event) => {
                try {
                    const data = JSON.parse(event.target.result);
                    importData(data);
                    showToast("JSON imported.");
                } catch (error) {
                    showToast("Invalid JSON file.");
                }
            };
            reader.readAsText(file);
        }

        document
            .getElementById("importJsonBtn")
            ?.addEventListener("click", () => {
                importFileInput?.click();
            });

        importFileInput?.addEventListener("change", function () {
            importFile(this.files?.[0]);
            this.value = "";
        });

        document.addEventListener("dragover", (event) => {
            if (!eventHasFiles(event)) return;
            event.preventDefault();
        });

        document.addEventListener("drop", (event) => {
            if (!eventHasFiles(event)) return;
            event.preventDefault();
            importFile(event.dataTransfer.files?.[0]);
        });
    }

    function escapeReportHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    function reportValue(value, fallback = "Not provided") {
        const normalized = value && String(value).trim();
        return escapeReportHtml(normalized || fallback);
    }

    function reportMetaGrid(fields) {
        return `<dl class="meta-grid">${fields
            .map(
                ([label, value]) => `
                    <div class="meta-item">
                        <dt>${escapeReportHtml(label)}</dt>
                        <dd>${reportValue(value)}</dd>
                    </div>`,
            )
            .join("")}</dl>`;
    }

    function reportNarrative(label, value) {
        return `
            <div class="narrative-block">
                <h3>${escapeReportHtml(label)}</h3>
                <div class="narrative-text">${reportValue(value)}</div>
            </div>`;
    }

    function reportList(values) {
        if (!Array.isArray(values) || !values.length) {
            return '<p class="empty-value">None selected</p>';
        }

        return `<ul class="report-list">${values
            .map((value) => `<li>${reportValue(value)}</li>`)
            .join("")}</ul>`;
    }

    function reportSection(title, content, className = "") {
        return `
            <section class="report-section ${className}">
                <div class="section-heading">
                    <span></span>
                    <h2>${escapeReportHtml(title)}</h2>
                </div>
                ${content}
            </section>`;
    }

    function openPdfReport({ filename, title, subtitle, body }) {
        const printWindow = window.open("", "_blank");
        if (!printWindow) {
            showToast("Allow pop-ups to export the PDF.");
            return false;
        }

        const generatedOn = new Date().toLocaleDateString("en-CA", {
            year: "numeric",
            month: "long",
            day: "numeric",
        });

        printWindow.document.write(`<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>${escapeReportHtml(filename)}</title>
    <style>
        * { box-sizing: border-box; }
        @page { size: A4; margin: 15mm 14mm 17mm; }
        :root {
            --ink: #18233b;
            --muted: #657084;
            --line: #dce2ea;
            --wash: #f4f7fa;
            --gold: #d9b300;
            --blue: #3f6595;
            --red: #a83c3c;
            --green: #316d48;
        }
        body {
            margin: 0;
            color: var(--ink);
            background: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .report-shell { max-width: 182mm; margin: 0 auto; }
        .report-header {
            display: grid;
            grid-template-columns: auto 1fr auto;
            align-items: center;
            gap: 16px;
            padding-bottom: 16px;
            border-bottom: 3px solid var(--ink);
            break-inside: avoid;
        }
        .brand-mark {
            width: 48px;
            height: 48px;
            display: grid;
            place-items: center;
            border: 2px solid var(--ink);
            font-size: 9px;
            font-weight: 800;
            letter-spacing: 0.08em;
            line-height: 1.1;
            text-align: center;
        }
        .brand-mark strong { display: block; font-size: 15px; }
        .eyebrow {
            margin-bottom: 2px;
            color: var(--blue);
            font-size: 8px;
            font-weight: 800;
            letter-spacing: 0.13em;
            text-transform: uppercase;
        }
        h1 { margin: 0; font-size: 20px; line-height: 1.15; letter-spacing: -0.02em; }
        .subtitle { margin: 5px 0 0; color: var(--muted); font-size: 9px; }
        .document-label {
            align-self: start;
            padding: 5px 8px;
            border-radius: 999px;
            color: var(--ink);
            background: #f4e9a8;
            font-size: 7px;
            font-weight: 800;
            letter-spacing: 0.12em;
        }
        .meta-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1px;
            margin: 18px 0 0;
            padding: 1px;
            border-radius: 6px;
            background: var(--line);
            overflow: hidden;
            break-inside: avoid;
        }
        .meta-item { min-height: 49px; padding: 9px 11px; background: var(--wash); }
        .meta-item dt {
            margin-bottom: 2px;
            color: var(--muted);
            font-size: 7px;
            font-weight: 800;
            letter-spacing: 0.09em;
            text-transform: uppercase;
        }
        .meta-item dd { margin: 0; font-size: 10px; font-weight: 650; }
        .report-section { margin-top: 20px; }
        .report-section.keep-together, .narrative-block, .summary-card { break-inside: avoid; }
        .section-heading {
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 10px;
            break-after: avoid;
        }
        .section-heading span { width: 18px; height: 3px; background: var(--gold); }
        .section-heading h2 {
            margin: 0;
            font-size: 12px;
            line-height: 1.2;
            letter-spacing: 0.015em;
        }
        .narrative-block {
            margin-top: 9px;
            padding: 12px 13px;
            border: 1px solid var(--line);
            border-left: 3px solid var(--blue);
            border-radius: 5px;
        }
        .narrative-block h3 {
            margin: 0 0 5px;
            color: var(--blue);
            font-size: 8px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .narrative-text { white-space: pre-wrap; overflow-wrap: anywhere; }
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 9px;
            break-inside: avoid;
        }
        .summary-card {
            padding: 12px 13px;
            border-radius: 5px;
            background: var(--wash);
        }
        .summary-card .label {
            color: var(--muted);
            font-size: 7px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .summary-card .value { margin-top: 4px; font-size: 11px; font-weight: 750; }
        .report-list { margin: 0; padding: 0; list-style: none; }
        .report-list li {
            position: relative;
            margin-top: 5px;
            padding: 8px 10px 8px 25px;
            border-radius: 4px;
            background: var(--wash);
            break-inside: avoid;
        }
        .report-list li::before {
            content: "";
            position: absolute;
            left: 10px;
            top: 13px;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--gold);
        }
        .empty-value { margin: 0; color: var(--muted); font-style: italic; }
        .rating-group { margin-top: 12px; }
        .rating-group h3 {
            margin: 0 0 5px;
            padding: 7px 9px;
            color: #fff;
            background: var(--ink);
            font-size: 9px;
            break-after: avoid;
        }
        .rating-table { width: 100%; border-collapse: collapse; }
        .rating-table tr { break-inside: avoid; }
        .rating-table td { padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
        .rating-table td:last-child { width: 37%; text-align: right; }
        .rating-pill {
            display: inline-block;
            padding: 3px 7px;
            border-radius: 999px;
            color: var(--blue);
            background: #eaf0f7;
            font-size: 8px;
            font-weight: 750;
            white-space: nowrap;
        }
        .rating-pill.low { color: var(--red); background: #f8e8e8; }
        .rating-pill.strong { color: var(--green); background: #e7f2eb; }
        .rating-pill.muted { color: var(--muted); background: #edf0f3; }
        .report-footer {
            margin-top: 24px;
            padding-top: 9px;
            border-top: 1px solid var(--line);
            color: var(--muted);
            font-size: 7px;
            text-align: center;
        }
        @media screen {
            body { padding: 28px; background: #edf1f5; }
            .report-shell {
                padding: 15mm 14mm 17mm;
                background: #fff;
                box-shadow: 0 18px 48px rgba(24, 35, 59, 0.14);
            }
        }
        @media print {
            body { background: #fff; }
            .report-shell { max-width: none; }
        }
    </style>
</head>
<body>
    <article class="report-shell">
        <header class="report-header">
            <div class="brand-mark"><div><strong>UW</strong>CO-OP</div></div>
            <div>
                <div class="eyebrow">Employer evaluation</div>
                <h1>${escapeReportHtml(title)}</h1>
                <p class="subtitle">${escapeReportHtml(subtitle)}</p>
            </div>
            <div class="document-label">INTERNAL</div>
        </header>
        <main>${body}</main>
        <footer class="report-footer">
            Generated ${escapeReportHtml(generatedOn)} · Convenience copy - not formally sanctioned by the University of Waterloo
        </footer>
    </article>
</body>
</html>`);
        printWindow.document.close();

        setTimeout(() => {
            printWindow.focus();
            printWindow.print();
        }, 250);
        return true;
    }

    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            applyTheme(html.dataset.theme === "dark" ? "light" : "dark");
        });
    }
    applyTheme(localStorage.getItem(THEME_KEY) || "light");

    function initMidTerm() {
        const STORAGE_KEY = "uw_draft";
        const FIELDS = [
            "pi_student",
            "pi_student_id",
            "pi_org",
            "pi_division",
            "pi_job_title",
            "pi_term",
            "pi_supervisor",
            "pi_supervisor_email",
            "q_your_name",
            "q_your_email",
            "q_your_phone",
            "q_expectations",
            "q_expectations_comments",
            "q_eem_questions",
            "q_strength",
            "q_strength_comments",
            "q_development",
            "q_development_comments",
        ];

        function getFormData() {
            const data = {};
            FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                if (element) data[id] = element.value;
            });
            return data;
        }

        function setFormData(data) {
            FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                if (element && data[id] !== undefined) {
                    element.value = data[id];
                }
            });
        }

        function clearForm() {
            FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                if (element) element.value = "";
            });
        }

        function saveDraft(showMessage = false) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(getFormData()));
            if (showMessage) showToast("Draft saved.");
        }

        document.addEventListener("input", (event) => {
            const target = event.target;
            if (target.id && FIELDS.includes(target.id)) {
                saveDraft();
            }
        });

        document.addEventListener("change", (event) => {
            const target = event.target;
            if (target.id && FIELDS.includes(target.id)) {
                saveDraft();
            }
        });

        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
            try {
                setFormData(JSON.parse(saved));
            } catch (error) {
                showToast("Saved draft could not be restored.");
            }
        }

        document.getElementById("saveDraftBtn")?.addEventListener("click", () => {
            saveDraft(true);
        });

        document.getElementById("clearBtn")?.addEventListener("click", () => {
            if (!confirm("Clear all fields?")) return;
            clearForm();
            localStorage.removeItem(STORAGE_KEY);
            showToast("Form cleared.");
        });

        document
            .getElementById("exportJsonBtn")
            ?.addEventListener("click", () => {
                const data = getFormData();
                const student = sanitizedFileSegment(data.pi_student, "student");
                const term = sanitizedFileSegment(data.pi_term, "term");
                downloadBlob(
                    new Blob([JSON.stringify(data, null, 2)], {
                        type: "application/json",
                    }),
                    `${datePrefix()}-uw-checkin-${student}-${term}.json`,
                );
                showToast("JSON exported.");
            });

        setupJsonImport((data) => {
            setFormData(data);
            saveDraft();
        });

        document.getElementById("exportPdfBtn")?.addEventListener("click", () => {
            const data = getFormData();
            const student = sanitizedFileSegment(data.pi_student, "student");
            const term = sanitizedFileSegment(data.pi_term, "term");
            const filename = `${datePrefix()}-uw-checkin-${student}-${term}.pdf`;
            const placement = reportMetaGrid([
                ["Student name", data.pi_student],
                ["Supervisor", data.pi_supervisor || data.q_your_name],
            ]);
            const progressSummary = `
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="label">Performance to date</div>
                        <div class="value">${reportValue(data.q_expectations, "Not answered")}</div>
                    </div>
                    <div class="summary-card">
                        <div class="label">Follow-up requested</div>
                        <div class="value">${reportValue(data.q_eem_questions, "Not answered")}</div>
                    </div>
                </div>
                ${reportNarrative("Performance and conduct comments", data.q_expectations_comments)}`;
            const developmentSummary = `
                <div class="summary-grid">
                    <div class="summary-card">
                        <div class="label">Top area of strength</div>
                        <div class="value">${reportValue(data.q_strength)}</div>
                    </div>
                    <div class="summary-card">
                        <div class="label">Area for development</div>
                        <div class="value">${reportValue(data.q_development)}</div>
                    </div>
                </div>
                ${reportNarrative("Strength comments", data.q_strength_comments)}
                ${reportNarrative("Development comments", data.q_development_comments)}`;

            const reportOpened = openPdfReport({
                filename,
                title: "Employer eCheckIn",
                subtitle: `${data.pi_student?.trim() || "Student"} · Mid-term progress review`,
                body: `${placement}${reportSection("Progress check", progressSummary)}${reportSection("Strengths and development", developmentSummary)}`,
            });
            if (reportOpened) {
                showToast("PDF report opened. Choose Save as PDF.");
            }
        });
    }

    function initEndTerm() {
        const STORAGE_KEY = "uw_end_term_draft";

        const RATING_CHOICES = [
            { value: "Not observed", short: "N.O.", text: "Not observed" },
            { value: "1 - Poor performance", short: "1", text: "Poor performance" },
            {
                value: "2 - Developing performance",
                short: "2",
                text: "Developing performance",
            },
            { value: "3 - Good performance", short: "3", text: "Good performance" },
            { value: "4 - Strong performance", short: "4", text: "Strong performance" },
        ];

        const COMPETENCY_SECTIONS = [
            {
                id: "expand_transfer_expertise",
                title: "Expand and Transfer Expertise",
                items: [
                    "learn job duties and work processes",
                    "locate, evaluate, and use information effectively",
                    "draw reasoned conclusions from multiple sources of information",
                    "learn and employ technical skills necessary for the role",
                    "apply skills and prior knowledge from academic program and/or previous work experience",
                ],
            },
            {
                id: "design_deliver_solutions",
                title: "Design and Deliver Solutions",
                items: [
                    "deliver quality work",
                    "meet deadlines and cope with workplace pressures",
                    "analyze problems and evaluate alternative solutions",
                    "engage in work with curiosity; ask questions to understand more than the work assigned",
                    "identify opportunities for improvement within the team and/or organization",
                ],
            },
            {
                id: "develop_self",
                title: "Develop Self",
                items: [
                    "adapt to changing priorities and circumstances",
                    "recognize limits of knowledge, skills and abilities",
                    "respond well to direction and incorporate feedback on performance",
                    "seek new tasks and responsibilities",
                    "seek opportunities to learn",
                ],
            },
            {
                id: "build_relationships",
                title: "Build Relationships",
                items: [
                    "write clearly and effectively",
                    "orally convey ideas and information clearly and effectively",
                    "collaborate well with others; both co-workers and supervisor/senior leaders",
                    "demonstrate ethical conduct in the workplace",
                    "show understanding and sensitivity to the needs and differences of others in the workplace (e.g. ethnicity, religion, language, etc.)",
                ],
            },
        ];

        const FRAMEWORK_OPTIONS = [
            "Discipline and context specific skills",
            "Information and data literacy",
            "Technological agility",
            "Self-management",
            "Self-assessment",
            "Lifelong learning and career development",
            "Communication",
            "Collaboration",
            "Intercultural effectiveness",
            "Innovation mindset",
            "Critical thinking",
            "Implementation",
        ];

        const TEXT_FIELDS = [
            "pi_student",
            "pi_student_id",
            "pi_org",
            "pi_division",
            "pi_job_title",
            "pi_term",
            "pi_supervisor",
            "pi_supervisor_email",
            "q_your_name",
            "q_your_title",
            "q_your_phone",
            "q_strength_comments",
            "q_development_comments",
            "q_overall_rating",
            "q_supervisor_comments",
            "q_supervisor_recommendations",
            "q_reviewed_with_student",
            "q_student_comments",
            "q_return_next_term",
        ];

        const CHECKBOX_GROUPS = {
            q_strengths: { options: FRAMEWORK_OPTIONS, max: 3 },
            q_developments: { options: FRAMEWORK_OPTIONS, max: 3 },
        };

        const RADIO_GROUPS = COMPETENCY_SECTIONS.flatMap((section) =>
            section.items.map((_, index) => `${section.id}_${index}`),
        );

        const form = document.getElementById("evaluationForm");
        const lowRatingModal = document.getElementById("lowRatingModal");
        const lowRatingYesBtn = document.getElementById("lowRatingYesBtn");
        const lowRatingNoBtn = document.getElementById("lowRatingNoBtn");
        let pendingExport = null;

        function hasLowRatings(data) {
            return RADIO_GROUPS.some((groupName) =>
                /^(1|2)\s-/.test(data[groupName] || ""),
            );
        }

        function closeLowRatingModal() {
            pendingExport = null;
            lowRatingModal?.close();
            document.getElementById("q_development_comments")?.focus();
        }

        function exportWithLowRatingCheck(exportAction) {
            const data = getFormData();

            if (!hasLowRatings(data)) {
                exportAction(data);
                return;
            }

            pendingExport = () => exportAction(data);
            lowRatingModal?.showModal();
        }

        lowRatingYesBtn?.addEventListener("click", () => {
            const exportAction = pendingExport;
            pendingExport = null;
            lowRatingModal?.close();
            exportAction?.();
        });

        lowRatingNoBtn?.addEventListener("click", closeLowRatingModal);

        lowRatingModal?.addEventListener("cancel", (event) => {
            event.preventDefault();
            closeLowRatingModal();
        });

        function escapeHtml(value) {
            return String(value)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
        }

        function renderCompetencies() {
            const container = document.getElementById("competencySections");
            if (!container) return;

            container.innerHTML = COMPETENCY_SECTIONS.map((section) => {
                const rows = section.items
                    .map((item, index) => {
                        const groupName = `${section.id}_${index}`;
                        const options = RATING_CHOICES.map(
                            (choice) => `
            <label class="rating-option">
              <input type="radio" name="${groupName}" value="${escapeHtml(choice.value)}">
              <span class="rating-option__card">
                <span class="rating-option__short">${escapeHtml(choice.short)}</span>
                <span class="rating-option__text">${escapeHtml(choice.text)}</span>
              </span>
            </label>
          `,
                        ).join("");

                        return `
            <div class="rating-row">
              <div class="rating-row__label">${escapeHtml(item)}</div>
              <div class="rating-options">${options}</div>
            </div>
          `;
                    })
                    .join("");

                return `
          <div class="competency-group">
            <div class="competency-group__title">${escapeHtml(section.title)}</div>
            <div class="competency-group__intro">Student demonstrates the ability to:</div>
            ${rows}
          </div>
        `;
            }).join("");
        }

        function renderCheckboxGroup(containerId, groupName, options) {
            const container = document.getElementById(containerId);
            if (!container) return;

            container.innerHTML = options
                .map(
                    (option) => `
        <label class="checkbox-option">
          <input type="checkbox" name="${groupName}" value="${escapeHtml(option)}">
          <span class="checkbox-option__card">
            <span class="checkbox-option__label">${escapeHtml(option)}</span>
            <span class="checkbox-option__indicator" aria-hidden="true"></span>
          </span>
        </label>
      `,
                )
                .join("");
        }

        function getCheckboxValues(groupName) {
            return [...document.querySelectorAll(`input[name="${groupName}"]:checked`)].map(
                (input) => input.value,
            );
        }

        function getRadioValue(groupName) {
            const selected = document.querySelector(
                `input[name="${groupName}"]:checked`,
            );
            return selected ? selected.value : "";
        }

        function getFormData() {
            const data = {};

            TEXT_FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                data[id] = element ? element.value : "";
            });

            RADIO_GROUPS.forEach((groupName) => {
                data[groupName] = getRadioValue(groupName);
            });

            Object.keys(CHECKBOX_GROUPS).forEach((groupName) => {
                data[groupName] = getCheckboxValues(groupName);
            });

            return data;
        }

        function setTextValues(data) {
            TEXT_FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                if (element && data[id] !== undefined) {
                    element.value = data[id];
                }
            });
        }

        function setRadioValues(data) {
            RADIO_GROUPS.forEach((groupName) => {
                const inputs = document.querySelectorAll(`input[name="${groupName}"]`);
                inputs.forEach((input) => {
                    input.checked = data[groupName] === input.value;
                });
            });
        }

        function syncCheckboxGroupState(groupName) {
            const config = CHECKBOX_GROUPS[groupName];
            const inputs = [...document.querySelectorAll(`input[name="${groupName}"]`)];
            const checkedInputs = inputs.filter((input) => input.checked);

            if (!config.max) return;

            const reachedMax = checkedInputs.length >= config.max;
            inputs.forEach((input) => {
                input.disabled = reachedMax && !input.checked;
            });
        }

        function setCheckboxValues(data) {
            Object.entries(CHECKBOX_GROUPS).forEach(([groupName]) => {
                const selected = Array.isArray(data[groupName])
                    ? new Set(data[groupName])
                    : new Set();
                const inputs = document.querySelectorAll(`input[name="${groupName}"]`);
                inputs.forEach((input) => {
                    input.checked = selected.has(input.value);
                });
                syncCheckboxGroupState(groupName);
            });
        }

        function setFormData(data) {
            setTextValues(data);
            setRadioValues(data);
            setCheckboxValues(data);
        }

        function clearForm() {
            TEXT_FIELDS.forEach((id) => {
                const element = document.getElementById(id);
                if (element) element.value = "";
            });

            RADIO_GROUPS.forEach((groupName) => {
                document.querySelectorAll(`input[name="${groupName}"]`).forEach((input) => {
                    input.checked = false;
                });
            });

            Object.keys(CHECKBOX_GROUPS).forEach((groupName) => {
                document.querySelectorAll(`input[name="${groupName}"]`).forEach((input) => {
                    input.checked = false;
                    input.disabled = false;
                });
            });
        }

        function saveDraft(showMessage = false) {
            localStorage.setItem(STORAGE_KEY, JSON.stringify(getFormData()));
            if (showMessage) showToast("Draft saved.");
        }

        function handleCheckboxLimit(event) {
            const input = event.target;
            if (input.type !== "checkbox") return;

            const groupName = input.name;
            const config = CHECKBOX_GROUPS[groupName];
            if (!config) return;

            const checked = getCheckboxValues(groupName);
            if (config.max && checked.length > config.max) {
                input.checked = false;
                showToast(`You can only select ${config.max} options here.`);
            }

            syncCheckboxGroupState(groupName);
            saveDraft();
        }

        renderCompetencies();
        renderCheckboxGroup("strengthOptions", "q_strengths", FRAMEWORK_OPTIONS);
        renderCheckboxGroup("developmentOptions", "q_developments", FRAMEWORK_OPTIONS);

        form?.addEventListener("input", (event) => {
            const target = event.target;
            if (
                target.matches(
                    'input[type="text"], input[type="email"], input[type="tel"], textarea, select',
                )
            ) {
                saveDraft();
            }
        });

        form?.addEventListener("change", (event) => {
            const target = event.target;

            if (target.type === "radio") {
                saveDraft();
                return;
            }

            if (target.type === "checkbox") {
                handleCheckboxLimit(event);
                return;
            }

            if (target.tagName === "SELECT") {
                saveDraft();
            }
        });

        const savedDraft = localStorage.getItem(STORAGE_KEY);
        if (savedDraft) {
            try {
                setFormData(JSON.parse(savedDraft));
            } catch (error) {
                showToast("Saved draft could not be restored.");
            }
        } else {
            Object.keys(CHECKBOX_GROUPS).forEach(syncCheckboxGroupState);
        }

        document.getElementById("saveDraftBtn")?.addEventListener("click", () => {
            saveDraft(true);
        });

        document.getElementById("clearBtn")?.addEventListener("click", () => {
            if (!confirm("Clear all fields and remove the saved draft?")) return;
            clearForm();
            localStorage.removeItem(STORAGE_KEY);
            Object.keys(CHECKBOX_GROUPS).forEach(syncCheckboxGroupState);
            showToast("Form cleared.");
        });

        document
            .getElementById("exportJsonBtn")
            ?.addEventListener("click", () => {
                exportWithLowRatingCheck((data) => {
                    const student = sanitizedFileSegment(
                        data.pi_student,
                        "student",
                    );
                    const supervisor = sanitizedFileSegment(
                        data.q_your_name,
                        "supervisor",
                    );
                    downloadBlob(
                        new Blob([JSON.stringify(data, null, 2)], {
                            type: "application/json",
                        }),
                        `${datePrefix()}-uw-end-term-${student}-${supervisor}.json`,
                    );
                    showToast("JSON exported.");
                });
            });

        setupJsonImport((data) => {
            clearForm();
            setFormData(data);
            saveDraft();
        });

        document.getElementById("exportPdfBtn")?.addEventListener("click", () => {
            exportWithLowRatingCheck((data) => {
                const student = sanitizedFileSegment(data.pi_student, "student");
                const supervisor = sanitizedFileSegment(
                    data.q_your_name,
                    "supervisor",
                );
                const filename = `${datePrefix()}-uw-end-term-${student}-${supervisor}.pdf`;
                const placement = reportMetaGrid([
                    ["Student name", data.pi_student],
                    ["Supervisor", data.pi_supervisor || data.q_your_name],
                    ["Reviewed with student", data.q_reviewed_with_student],
                ]);
                const ratings = COMPETENCY_SECTIONS.map((section) => {
                    const rows = section.items
                        .map((item, index) => {
                            const value = data[`${section.id}_${index}`] || "Not rated";
                            let ratingClass = "";
                            if (/^(1|2)\s-/.test(value)) ratingClass = "low";
                            else if (/^4\s-/.test(value)) ratingClass = "strong";
                            else if (value === "Not observed" || value === "Not rated") {
                                ratingClass = "muted";
                            }

                            return `
                                <tr>
                                    <td>${escapeReportHtml(item)}</td>
                                    <td><span class="rating-pill ${ratingClass}">${reportValue(value)}</span></td>
                                </tr>`;
                        })
                        .join("");

                    return `
                        <div class="rating-group">
                            <h3>${escapeReportHtml(section.title)}</h3>
                            <table class="rating-table"><tbody>${rows}</tbody></table>
                        </div>`;
                }).join("");
                const strengths = `
                    ${reportList(data.q_strengths)}
                    ${reportNarrative("Supporting comments", data.q_strength_comments)}`;
                const development = `
                    ${reportList(data.q_developments)}
                    ${reportNarrative("Improvement guidance", data.q_development_comments)}`;
                const overall = `
                    <div class="summary-grid">
                        <div class="summary-card">
                            <div class="label">Overall performance</div>
                            <div class="value">${reportValue(data.q_overall_rating, "Not selected")}</div>
                        </div>
                        <div class="summary-card">
                            <div class="label">Return next term</div>
                            <div class="value">${reportValue(data.q_return_next_term, "Not selected")}</div>
                        </div>
                    </div>
                    ${reportNarrative("Supervisor comments", data.q_supervisor_comments)}
                    ${reportNarrative("Supervisor recommendations", data.q_supervisor_recommendations)}`;

                const reportOpened = openPdfReport({
                    filename,
                    title: "Employer End-of-Term Evaluation",
                    subtitle: `${data.pi_student?.trim() || "Student"} · Final performance review`,
                    body: `${placement}${reportSection("Competency ratings", ratings)}${reportSection("Top areas of strength", strengths)}${reportSection("Top areas for development", development)}${reportSection("Overall evaluation", overall)}${reportSection("Student comments", reportNarrative("Student perspective", data.q_student_comments))}`,
                });
                if (reportOpened) {
                    showToast("PDF report opened. Choose Save as PDF.");
                }
            });
        });
    }

    if (pageType === "mid-term") {
        initMidTerm();
    } else if (pageType === "end-term") {
        initEndTerm();
    }
})();
