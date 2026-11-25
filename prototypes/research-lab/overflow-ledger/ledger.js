/* The overflow ledger prototype (docs/OVERFLOW-LEDGER-CONTRACT-v1.md). Every figure is read from the research file
   when the page loads; nothing is typed here. An account of the model, not of measured bacteria. */
(function () {
  "use strict";
  var FILE = "../../../data/research/overflow_ledger.v1.json";
  var SHOW = 40;
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var num = function (v, dp) { return v == null ? '<span class="na">not given</span>' : Number(v).toLocaleString("en-GB", { minimumFractionDigits: dp, maximumFractionDigits: dp }); };
  var title = function (s) { return s == null ? "Name not given" : String(s).replace(/\//g, " ").replace(/\s+/g, " ").trim(); };
  var day = function (iso) { return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" }); };

  var doc, rows, state = { company: "all", sort: "weight_sum", all: false };
  var SORTS = [["weight_sum", "Summed weight"], ["weighted_spills", "Weighted spills a year"], ["spots_reached", "Spots reached"]];

  function build(d) {
    var o = d.overflows, out = [];
    for (var i = 0; i < o.site_id.length; i++) {
      var r = { i: i };
      Object.keys(o).forEach(function (k) { r[k] = o[k][i]; });
      out.push(r);
    }
    return out;
  }

  function front() {
    var c = doc.coverage, top = rows[0];
    $("front-answer").innerHTML = "<p>The model traces " + num(c.overflows, 0) + " monitored overflows to " + c.spots_with_overflows +
      " of the " + c.spots + " listed spots. " + num(c.overflows_reaching_one_spot, 0) + " of them reach one spot only. The largest summed weight is " +
      num(top.weight_sum, 2) + ", for " + esc(title(top.name)) + " (" + esc(doc.companies[top.company]) + "), across " + top.spots_reached + " spots.</p>";
    $("front-figs-body").innerHTML = "<p>" + num(c.links, 0) + " overflow-to-spot links in " + c.groups + " groups of spots that share an overflow. " +
      c.spots_no_overflow + " spots have no monitored overflow within " + doc.source_export.settings.max_upstream_km + " km upstream, and " +
      c.spots_off_network + " sit off the mapped rivers. " + c.overflows_without_average + " overflows have no long-term average in the annual return, " +
      "so no weighted spills a year.</p><p>Settings: river speed " + doc.source_export.settings.river_velocity_ms + " m/s, T90 " +
      doc.source_export.settings.t90_h + " hours, dilution \"" + esc(doc.source_export.settings.dilution_mode) + "\".</p>";
    $("front-figs").hidden = false;
    $("asof").textContent = "Weights as of " + day(doc.source_export.made) + ", from the forecast's own network trace. Refreshed by hand.";
    $("evidence-text").textContent = doc.claim.evidence.text + " (" + doc.claim.evidence.record + ", read " + day(doc.claim.evidence.read) + ".)";
    $("not").innerHTML = doc.claim.not_claimed.map(function (t) { return "<li>It does not say " + esc(t) + ".</li>"; }).join("") +
      "<li>" + esc(doc.definitions.season_figure_not_made) + "</li>";
    $("attrib").textContent = doc.attribution.join(". ") + ".";
  }

  function table() {
    var mine = rows.filter(function (r) { return state.company === "all" || doc.companies[r.company] === state.company; });
    var k = state.sort;
    mine.sort(function (a, b) { return (b[k] == null ? -1 : b[k]) - (a[k] == null ? -1 : a[k]) || b.weight_sum - a.weight_sum; });
    var shown = state.all ? mine : mine.slice(0, SHOW), max = Math.max.apply(null, mine.map(function (r) { return r.weight_sum; }).concat([0.0001]));
    $("table-aside").textContent = shown.length + " of " + mine.length + " shown";
    $("table").innerHTML = "<table><caption>Model weights, not measurements. A weight is survival × dilution, from 0 to 1.</caption><thead><tr>" +
      "<th>Overflow</th><th>Company</th><th class=\"n\">Spots reached</th><th class=\"n\">Summed weight</th><th class=\"n\">Largest weight</th>" +
      "<th>Where it is largest</th><th class=\"n\">Spills a year (EA average)</th><th class=\"n\">Weighted spills a year</th></tr></thead><tbody>" +
      shown.map(function (r) {
        return "<tr><td>" + esc(title(r.name)) + "<small>" + esc(r.water || "Watercourse not given") + " · " + esc(r.site_id) + "</small></td><td>" +
          esc(doc.companies[r.company]) + "</td><td class=\"n\">" + r.spots_reached + "</td><td class=\"n\">" + num(r.weight_sum, 2) +
          "<span class=\"bar\" style=\"width:" + (100 * r.weight_sum / max).toFixed(1) + "%\"></span></td><td class=\"n\">" + num(r.weight_max, 2) +
          "</td><td>" + esc(doc.spots[r.max_spot].name) + "</td><td class=\"n\">" + num(r.spills_a_year, 1) + "</td><td class=\"n\">" +
          num(r.weighted_spills, 1) + "</td></tr>";
      }).join("") + "</tbody></table>";
    var more = $("more");
    more.hidden = mine.length <= SHOW;
    more.textContent = state.all ? "Show the first " + SHOW : "Show all " + mine.length;
  }

  function companies() {
    $("companies").innerHTML = "<table><caption>Model weights added by company. Not a comparison of companies.</caption><thead><tr><th>Company</th>" +
      "<th class=\"n\">Overflows traced</th><th class=\"n\">Listed spots reached</th><th class=\"n\">Links</th><th class=\"n\">Summed weight</th>" +
      "<th class=\"n\">Weighted spills a year</th><th class=\"n\">Overflows with no average</th></tr></thead><tbody>" +
      doc.company.map(function (c) {
        return "<tr><td>" + esc(c.company) + "</td><td class=\"n\">" + c.overflows + "</td><td class=\"n\">" + c.spots + "</td><td class=\"n\">" + c.links +
          "</td><td class=\"n\">" + num(c.weight_sum, 1) + "</td><td class=\"n\">" + num(c.weighted_spills, 0) + "</td><td class=\"n\">" + c.no_average + "</td></tr>";
      }).join("") + "</tbody></table>";
  }

  function grid() {
    var g = doc.groups[Number($("group").value)], spots = g.spots;
    var mine = rows.filter(function (r) { return r.group === g.id; }).sort(function (a, b) { return b.weight_sum - a.weight_sum; });
    $("group-note").textContent = g.spots.length + (g.spots.length === 1 ? " spot, " : " spots, ") + g.overflows + " overflows, " + g.links +
      " links. Each cell is the model's weight for that overflow at that spot. A hatched cell means the model does not trace the overflow to the spot.";
    $("grid").innerHTML = "<table><caption>Model weights (survival × dilution, 0 to 1), not measurements.</caption><thead><tr><th>Overflow</th>" +
      spots.map(function (s) { return "<th class=\"n\">" + esc(doc.spots[s].name) + "</th>"; }).join("") + "<th class=\"n\">Summed</th></tr></thead><tbody>" +
      mine.map(function (r) {
        var by = {};
        r.links.forEach(function (ln) { by[ln[0]] = ln[1]; });
        return "<tr><td>" + esc(title(r.name)) + "<small>" + esc(doc.companies[r.company]) + "</small></td>" + spots.map(function (s) {
          return by[s] == null ? "<td class=\"none\" aria-label=\"not traced\"></td>" : "<td class=\"w\" style=\"--w:" + by[s] + "\">" + num(by[s], 2) + "</td>";
        }).join("") + "<td class=\"n\">" + num(r.weight_sum, 2) + "</td></tr>";
      }).join("") + "</tbody></table>";
    $("grid-key").innerHTML = "<span><i class=\"sw w1\"></i>darker: a larger weight</span><span><i class=\"sw gap\"></i>not traced to this spot</span>";
    try { history.replaceState(null, "", "#g=" + encodeURIComponent(doc.spots[g.spots[0]].id)); } catch (e) { /* a file: page */ }
  }

  function controls() {
    $("company").innerHTML = "<option value=\"all\">All companies</option>" + doc.company.map(function (c) { return "<option>" + esc(c.company) + "</option>"; }).join("");
    $("company").onchange = function () { state.company = this.value; state.all = false; table(); };
    $("sort").innerHTML = SORTS.map(function (s) { return "<button type=\"button\" data-k=\"" + s[0] + "\" aria-pressed=\"" + (s[0] === state.sort) + "\">" + s[1] + "</button>"; }).join("");
    $("sort").onclick = function (e) {
      var b = e.target.closest("button");
      if (!b) return;
      state.sort = b.dataset.k;
      Array.prototype.forEach.call(this.children, function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      table();
    };
    $("more").onclick = function () { state.all = !state.all; table(); };
    $("group").innerHTML = doc.groups.map(function (g) {
      return "<option value=\"" + g.id + "\">" + esc(g.name) + (g.spots.length > 1 ? " and " + (g.spots.length - 1) + " more" : "") + " (" + g.overflows + " overflows)</option>";
    }).join("");
    // the Wharfe above Ilkley unless the address names a spot (#g=<spot id>): the audit statement's place
    var want = decodeURIComponent((location.hash.match(/g=([^&]+)/) || [])[1] || "bw-uke4100-08901");
    var si = doc.spots.findIndex(function (s) { return s.id === want; });
    var hit = doc.groups.find(function (g) { return g.spots.indexOf(si) >= 0; });
    $("group").value = String(hit ? hit.id : 0);
    $("group").onchange = grid;
  }

  fetch(FILE).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).then(function (d) {
    if (d.schema !== "swimsignal.overflow-ledger" || String(d.version).split(".")[0] !== "1") throw new Error("schema");
    doc = d; rows = build(d);
    front(); controls(); table(); companies(); grid();
  }).catch(function () {
    $("front-answer").innerHTML = "<p>This page's data could not be loaded.</p>";
  });
})();
