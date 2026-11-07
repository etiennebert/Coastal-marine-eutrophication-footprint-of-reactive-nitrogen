const d = require("docx");
const fs = require("fs");

const F = "Times New Roman";
const W = [2130, 2950, 1880, 1400, 1000];           // DXA, sum 9360 = 6.5" on Letter
const NONE = { style: d.BorderStyle.NONE, size: 0, color: "FFFFFF" };
const LINE = (sz) => ({ style: d.BorderStyle.SINGLE, size: sz, color: "000000" });

// numbers: mean 2015-2022 from 1. results/CBA_vs_PBA (PBA, all pathways summed),
// computed by F_8_table1_data.py -> 2. figures/Table1_data.json
// rows: [site (ss), site mean total t O2-eq/yr, bordering countries,
//        [country, mean impact t O2-eq/yr, share %] x3 ]
const path = require("path");
const JSON_IN = path.join(__dirname, "2. figures", "Table1_data.json");
if (!fs.existsSync(JSON_IN)) { console.error("run  python F_8_table1_data.py  first"); process.exit(1); }
const T1 = JSON.parse(fs.readFileSync(JSON_IN, "utf8"));
const DATA = T1.data;
const JOINT = `${T1.joint_top3_pct[0]}–${T1.joint_top3_pct[1]}%`;

const txt = (t, opts = {}) => new d.TextRun({ text: t, font: F, size: 20, ...opts });
const para = (runs, opts = {}) =>
  new d.Paragraph({ children: runs, spacing: { before: 20, after: 20 }, ...opts });

function cell(runs, w, { vMerge = null, align = "left", borders = {} } = {}) {
  return new d.TableCell({
    width: { size: w, type: d.WidthType.DXA },
    verticalMerge: vMerge,
    verticalAlign: d.VerticalAlign.CENTER,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, ...borders },
    children: [para(runs, { alignment: align === "right" ? d.AlignmentType.RIGHT : d.AlignmentType.LEFT })],
  });
}

const HDR = [
  [[txt("Location (cLME-ss)", { bold: true })], W[0], "left"],
  [[txt("Countries around the LME", { bold: true })], W[1], "left"],
  [[txt("Emitting country", { bold: true })], W[2], "left"],
  [[txt("Impact (t O", { bold: true }), txt("2", { bold: true, subScript: true }),
    txt("-eq yr", { bold: true }), txt("−1", { bold: true, superScript: true }),
    txt(")", { bold: true })], W[3], "right"],
  [[txt("Share (%)", { bold: true })], W[4], "right"],
];
const rows = [];
rows.push(new d.TableRow({
  tableHeader: true,
  children: HDR.map(([runs, w, align]) =>
    cell(runs, w, { align, borders: { top: LINE(8), bottom: LINE(4) } })),
}));
// body: 7 blocks x 3 rows, vertical merges on the first two columns
DATA.forEach(([loc, sitetot, around, tops], bi) => {
  tops.forEach(([ctry, val, pct], ri) => {
    const last = bi === DATA.length - 1 && ri === 2;
    const bord = last ? { bottom: LINE(8) } : (ri === 2 ? { bottom: LINE(2) } : {});
    const locRuns = [txt(loc), new d.TextRun({ font: F, size: 18, break: 1, text: "" }),
                     txt("total " + sitetot + " t yr", { size: 18, color: "444444" }),
                     txt("−1", { size: 18, color: "444444", superScript: true })];
    rows.push(new d.TableRow({
      children: [
        ri === 0 ? cell(locRuns, W[0], { vMerge: d.VerticalMergeType.RESTART, borders: bord })
                 : cell([txt("")], W[0], { vMerge: d.VerticalMergeType.CONTINUE, borders: bord }),
        cell([txt(ri === 0 ? around : "")], W[1],
             { vMerge: ri === 0 ? d.VerticalMergeType.RESTART : d.VerticalMergeType.CONTINUE, borders: bord }),
        cell([txt(ctry)], W[2], { borders: bord }),
        cell([txt(val)], W[3], { align: "right", borders: bord }),
        cell([txt(pct)], W[4], { align: "right", borders: bord }),
      ],
    }));
  });
});

const capRuns = [
  txt("Table 1. ", { bold: true, size: 22 }),
  txt("Countries bordering each coral-reef cLME sub-segment and the top three countries producing its eutrophication impact (mean 2015–2022, all pathways summed). ", { size: 22 }),
  txt("For each sub-segment: the countries whose coastline borders it, and the three countries whose territorial emissions cause the largest share of its nitrogen-driven eutrophication (production-based accounting, summed over waterborne leaching, atmospheric NH", { size: 22 }),
  txt("3", { size: 22, subScript: true }),
  txt(" and NO", { size: 22 }),
  txt("x", { size: 22, subScript: true }),
  txt("). Impacts are mean annual values over 2015–2022, in tonnes of O", { size: 22 }),
  txt("2", { size: 22, subScript: true }),
  txt("-eq per year (three significant figures); the grey figure under each site name is the sub-segment’s mean total impact. Shares are relative to that total; the three leading producers jointly account for " + JOINT + " of each sub-segment’s burden.", { size: 22 }),
];
const notes = [
  new d.Paragraph({ spacing: { before: 80 }, children: [
    txt("† Emitter does not border the sub-segment — its contribution arrives by atmospheric transport (or, for waterborne inputs, through shared river basins).  ", { size: 18 }),
  ]}),
  new d.Paragraph({ children: [ txt("* GLORIA aggregate region (“Rest of Asia-Pacific”).", { size: 18 }) ]}),
];

const doc = new d.Document({
  styles: { default: { document: { run: { font: F, size: 20 } } } },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 },
                          margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
    children: [
      new d.Paragraph({ spacing: { after: 160 }, children: capRuns }),
      new d.Table({ columnWidths: W, width: { size: 9360, type: d.WidthType.DXA }, rows }),
      ...notes,
    ],
  }],
});

d.Packer.toBuffer(doc).then(b => { const out = path.join(__dirname, "2. figures", "Table1_producing_countries.docx"); fs.writeFileSync(out, b); console.log("written -> " + out); });
