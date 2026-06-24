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

    function markdownValue(value, fallback = "_(not provided)_") {
        return value && String(value).trim()
            ? String(value).trim()
            : fallback;
    }

    function markdownList(values, fallback = "_(none selected)_") {
        return values && values.length
            ? values.map((value) => `- ${value}`).join("\n")
            : fallback;
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

        document.getElementById("exportMdBtn")?.addEventListener("click", () => {
            const data = getFormData();
            const val = (id) => data[id] || "_(not provided)_";
            const opt = (id) => data[id] || "_(not answered)_";

            const md = `# UW Co-op Employer eCheckIn

## Placement Information

| Field | Value |
|---|---|
| Student Name | ${val("pi_student")} |
| Student ID | ${val("pi_student_id")} |
| Organization | ${val("pi_org")} |
| Division | ${val("pi_division")} |
| Job Title | ${val("pi_job_title")} |
| Term | ${val("pi_term")} |
| Supervisor | ${val("pi_supervisor")} |
| Supervisor Email | ${val("pi_supervisor_email")} |

---

## Your Information

| Field | Value |
|---|---|
| Name | ${val("q_your_name")} |
| Email | ${val("q_your_email")} |
| Phone | ${val("q_your_phone")} |

---

## Your Feedback - Required

**Q: Overall, how is the student meeting your expectations with respect to their job performance and conduct at work? (Please note that your Employer Experience Manager will follow up with you if the student is not meeting expectations).**

${opt("q_expectations")}

**Comments (re: student job performance and conduct):**

${data.q_expectations_comments || "_(not provided)_"}

**Q: Do you have any other questions or concerns that you would like to talk about with your Employer Experience Manager (eg. funding, events, hiring strategy, engagement at UW beyond co-op, etc.)?**

${opt("q_eem_questions")}

---

## Additional Required Feedback

**Top area of strength:**

${opt("q_strength")}

**Additional comments on area of strength:**

${data.q_strength_comments || "_(not provided)_"}

**Area for development:**

${opt("q_development")}

**Additional comments on area for development:**

${data.q_development_comments || "_(not provided)_"}
`;

            const student = sanitizedFileSegment(data.pi_student, "student");
            const term = sanitizedFileSegment(data.pi_term, "term");
            downloadBlob(
                new Blob([md], { type: "text/markdown" }),
                `${datePrefix()}-uw-checkin-${student}-${term}.md`,
            );
            showToast("Markdown exported.");
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
                const data = getFormData();
                const student = sanitizedFileSegment(data.pi_student, "student");
                const term = sanitizedFileSegment(data.pi_term, "term");
                downloadBlob(
                    new Blob([JSON.stringify(data, null, 2)], {
                        type: "application/json",
                    }),
                    `${datePrefix()}-uw-end-term-${student}-${term}.json`,
                );
                showToast("JSON exported.");
            });

        setupJsonImport((data) => {
            clearForm();
            setFormData(data);
            saveDraft();
        });

        document.getElementById("exportMdBtn")?.addEventListener("click", () => {
            const data = getFormData();
            const competencyMarkdown = COMPETENCY_SECTIONS.map((section) => {
                const items = section.items
                    .map((item, index) => {
                        const key = `${section.id}_${index}`;
                        return `- ${item}: ${markdownValue(data[key], "_(not rated)_")}`;
                    })
                    .join("\n");

                return `### ${section.title}\n\n${items}`;
            }).join("\n\n");

            const md = `# UW Co-op Employer End-of-Term Evaluation

## Placement Information

- Student Name: ${markdownValue(data.pi_student)}
- Student ID: ${markdownValue(data.pi_student_id)}
- Organization: ${markdownValue(data.pi_org)}
- Division / Department: ${markdownValue(data.pi_division)}
- Job Title: ${markdownValue(data.pi_job_title)}
- Work Term: ${markdownValue(data.pi_term)}
- Supervisor: ${markdownValue(data.pi_supervisor)}
- Supervisor Email: ${markdownValue(data.pi_supervisor_email)}

## Your Information

- Name: ${markdownValue(data.q_your_name)}
- Title: ${markdownValue(data.q_your_title)}
- Phone: ${markdownValue(data.q_your_phone)}

## Rating Details

${competencyMarkdown}

## Top 3 Areas of Strength

${markdownList(data.q_strengths)}

### Additional Comments

${markdownValue(data.q_strength_comments)}

## Top 3 Areas for Development

${markdownList(data.q_developments)}

### Additional Comments

${markdownValue(data.q_development_comments)}

## Overall Evaluation

- Overall Performance Rating: ${markdownValue(data.q_overall_rating, "_(not selected)_")}
- Reviewed Completed Evaluation With Student: ${markdownValue(data.q_reviewed_with_student, "_(not selected)_")}

### Supervisor's Comments

${markdownValue(data.q_supervisor_comments)}

### Supervisor's Recommendations

${markdownValue(data.q_supervisor_recommendations)}

## Student Comments

${markdownValue(data.q_student_comments)}

## Future Employment Potential

- Would You Like the Student to Return Next Work Term: ${markdownValue(data.q_return_next_term, "_(not selected)_")}
`;

            const student = sanitizedFileSegment(data.pi_student, "student");
            const term = sanitizedFileSegment(data.pi_term, "term");
            downloadBlob(
                new Blob([md], { type: "text/markdown" }),
                `${datePrefix()}-uw-end-term-${student}-${term}.md`,
            );
            showToast("Markdown exported.");
        });
    }

    if (pageType === "mid-term") {
        initMidTerm();
    } else if (pageType === "end-term") {
        initEndTerm();
    }
})();
