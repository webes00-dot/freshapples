'use strict';

const categories = [['Flower', 'Flower'], ['Preroll', 'Pre-rolls'], ['Concentrates', 'Concentrates']];
const periods = [[0, 'Latest'], [-1, 'Previous observation'], [30, 'About 1 month'], [90, 'About 3 months'], [180, 'About 6 months']];
const dayLength = 86_400_000;
const currency = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'});
const dateFormat = new Intl.DateTimeFormat('en-US', {month: 'short', day: 'numeric', timeZone: 'UTC'});

function node(tag, value, className) {
  const element = document.createElement(tag);
  if (value) element.textContent = value;
  if (className) element.className = className;
  return element;
}

function datedComparison(entries, category, offset) {
  const available = entries.filter(([, metrics]) => metrics[category]);
  if (!available.length) return null;
  if (offset === 0) return available[0];
  if (offset === -1) return available[1] || null;
  const target = Date.parse(entries[0][0]) - offset * dayLength;
  return available.reduce((closest, entry) => {
    const distance = Math.abs(Date.parse(entry[0]) - target);
    return distance <= 7 * dayLength &&
      (!closest || distance < Math.abs(Date.parse(closest[0]) - target)) ? entry : closest;
  }, null);
}

async function renderHistory() {
  const status = document.getElementById('history-status');
  const request = await fetch('data/market-price-history.json', {cache: 'no-cache'});
  if (!request.ok) throw new Error('History request failed');
  const history = await request.json();
  const entries = Object.entries(history.days).sort(([a], [b]) => b.localeCompare(a));
  if (!entries.length) {
    status.textContent = 'Comparable crawl history will appear after the first qualifying scan.';
    return;
  }

  const chart = document.getElementById('history-chart');
  const comparisons = categories.map(([category, label]) => ({
    category, label, points: periods.map(([offset, period]) => ({
      period, entry: datedComparison(entries, category, offset),
    })),
  }));
  const values = comparisons.flatMap(({category, points}) =>
    points.filter(({entry}) => entry).map(({entry}) => entry[1][category].median));
  const maximum = Math.max(1, ...values);
  for (const {category, label, points} of comparisons) {
    const section = node('div', '', 'market-series');
    section.append(node('h3', label));
    for (const {period, entry} of points) {
      const row = node('div', '', 'market-bar-row');
      row.append(node('span', period));
      const bar = node('div', '', 'market-bar');
      bar.setAttribute('aria-hidden', 'true');
      bar.style.width = entry ? (entry[1][category].median / maximum * 100) + '%' : '0';
      row.append(bar, node('strong', entry ? currency.format(entry[1][category].median) : '—'));
      if (entry) {
        const [day, metrics] = entry;
        row.firstChild.textContent += ' · ' + dateFormat.format(new Date(day));
        row.lastChild.title = metrics[category].offers + ' offers at ' + metrics[category].retailers + ' retailers';
      }
      section.append(row);
    }
    chart.append(section);
  }

  const body = document.getElementById('history-rows');
  for (const [day, metrics] of entries) {
    const row = node('tr');
    const heading = node('th', day);
    heading.scope = 'row';
    row.append(heading);
    for (const [category] of categories) {
      const point = metrics[category];
      row.append(node('td', point ? currency.format(point.median) + '/g · ' + point.offers + ' offers' : '—'));
    }
    body.append(row);
  }

  const recentDays = entries.length;
  status.textContent = recentDays + ' observed date' + (recentDays === 1 ? '' : 's') + ' available. Latest and previous observation are distinct dated crawls; 1-, 3- and 6-month comparisons require an observation within seven days of each target date. Coverage varies by crawl.';
  chart.hidden = false;
  document.getElementById('history-details').hidden = false;
}

renderHistory().catch(() => {
  document.getElementById('history-status').textContent = 'Menu history is temporarily unavailable.';
});
