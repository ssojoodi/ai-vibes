// PDF report rendering for both evaluation forms.
(() => {
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
        .selected-rating-guidance {
            --guidance-accent: var(--blue);
            margin-top: 9px;
            padding: 12px 13px;
            border: 1px solid var(--line);
            border-left: 3px solid var(--guidance-accent);
            border-radius: 5px;
            background: #fbfcfd;
            break-inside: avoid;
        }
        .selected-rating-guidance[data-tone="outstanding"] { --guidance-accent: #9a7600; }
        .selected-rating-guidance[data-tone="positive"] { --guidance-accent: var(--green); }
        .selected-rating-guidance[data-tone="caution"] { --guidance-accent: #a75f12; }
        .selected-rating-guidance[data-tone="critical"] { --guidance-accent: var(--red); }
        .selected-rating-guidance .label {
            color: var(--guidance-accent);
            font-size: 7px;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .selected-rating-guidance h3 { margin: 3px 0 7px; font-size: 11px; }
        .selected-rating-guidance ul { margin: 0; padding-left: 17px; }
        .selected-rating-guidance li + li { margin-top: 4px; }
        .selected-rating-guidance p { margin: 7px 0 0; }
        .selected-rating-guidance a { color: var(--blue); font-weight: 700; }
        .selected-rating-guidance__note {
            padding: 7px 8px;
            border-radius: 4px;
            font-weight: 700;
            background: var(--wash);
        }
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
        function overallRatingGuidanceReportHtml(ratingValue, OVERALL_RATING_GUIDANCE) {
            const guidance = OVERALL_RATING_GUIDANCE[ratingValue];
            if (!guidance) return "";

            const criteria = guidance.criteria
                .map((criterion) => `<li>${escapeReportHtml(criterion)}</li>`)
                .join("");
            const note = guidance.note
                ? `<p class="selected-rating-guidance__note">${escapeReportHtml(guidance.note)}</p>`
                : "";
            const award = guidance.award
                ? `<p>${escapeReportHtml(guidance.award.text)} <a href="${escapeReportHtml(guidance.award.url)}">${escapeReportHtml(guidance.award.label)}</a>.</p>`
                : "";

            return `
                <div class="selected-rating-guidance" data-tone="${escapeReportHtml(guidance.tone)}">
                    <div class="label">Selected rating guidance</div>
                    <h3>${escapeReportHtml(guidance.label)}</h3>
                    <ul>${criteria}</ul>
                    ${award}
                    ${note}
                </div>`;
        }

    function midTerm(data, filename) {
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

            return openPdfReport({
                filename,
                title: "Employer eCheckIn",
                subtitle: `${data.pi_student?.trim() || "Student"} · Mid-term progress review`,
                body: `${placement}${reportSection("Progress check", progressSummary)}${reportSection("Strengths and development", developmentSummary)}`,
            });
    }
    function endTerm(data, filename, COMPETENCY_SECTIONS, OVERALL_RATING_GUIDANCE) {
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
                    ${overallRatingGuidanceReportHtml(data.q_overall_rating, OVERALL_RATING_GUIDANCE)}
                    ${reportNarrative("Supervisor comments", data.q_supervisor_comments)}
                    ${reportNarrative("Supervisor recommendations", data.q_supervisor_recommendations)}`;

                return openPdfReport({
                    filename,
                    title: "Employer End-of-Term Evaluation",
                    subtitle: `${data.pi_student?.trim() || "Student"} · Final performance review`,
                    body: `${placement}${reportSection("Competency ratings", ratings)}${reportSection("Top areas of strength", strengths)}${reportSection("Top areas for development", development)}${reportSection("Overall evaluation", overall)}${reportSection("Student comments", reportNarrative("Student perspective", data.q_student_comments))}`,
                });
    }
    window.EvaluationPdf = Object.freeze({ midTerm, endTerm });
})();
