(() => {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const dateFormat = new Intl.DateTimeFormat('en-US', {
    month: 'short', year: 'numeric', timeZone: 'UTC'
  });
  const money = new Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'});
  const charts = [
    {
      title: 'Flower and pre-rolls',
      step: 4,
      height: 360,
      categories: [['Flower', '#27764f'], ['Pre-rolls', '#9a5925']]
    },
    {
      title: 'Concentrates',
      step: 15,
      height: 235,
      categories: [['Concentrates', '#39728f']]
    }
  ];

  function monthIndex(value) {
    const [year, month] = value.split('-').map(Number);
    return year * 12 + month - 1;
  }

  function monthLabel(index) {
    return dateFormat.format(new Date(Date.UTC(Math.floor(index / 12), index % 12, 1)));
  }

  function svgElement(parent, tag, attributes, content) {
    const element = document.createElementNS(NS, tag);
    for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
    if (content !== undefined) element.textContent = content;
    parent.append(element);
    return element;
  }

  function renderPlot(container, chart, series, width) {
    const points = series.flatMap(item => item.points);
    const first = Math.min(...points.map(point => point.month));
    const last = Math.max(...points.map(point => point.month));
    const largest = Math.max(...points.map(point => point.price));
    const step = chart.step * Math.max(1, Math.ceil(largest / (6 * chart.step)));
    const topPrice = 6 * step;
    const height = width < 540 ? Math.min(chart.height, 270) : chart.height;
    const left = 43;
    const right = width - 78;
    const top = 27;
    const bottom = height - 37;
    const x = month => left + (month - first) / Math.max(1, last - first) * (right - left);
    const y = price => bottom - price / topPrice * (bottom - top);

    container.replaceChildren();
    const svg = svgElement(container, 'svg', {
      viewBox: '0 0 ' + width + ' ' + height,
      role: 'img',
      'aria-label': chart.title + ' monthly prices per gram'
    });
    svgElement(svg, 'desc', {}, series.map(({name, points}) => {
      const latest = points[points.length - 1];
      return name + ' was ' + money.format(latest.price) + ' per gram in ' + monthLabel(latest.month) + '.';
    }).join(' '));

    const text = (x, y, value, attrs = {}) => svgElement(svg, 'text', {
      x, y, fill: '#52685e', 'font-size': 12, ...attrs
    }, value);

    text(left, 15, 'Price per gram');
    for (let tick = 0; tick <= 6; tick++) {
      const price = tick * step;
      const row = y(price);
      svgElement(svg, 'line', {x1: left, x2: right, y1: row, y2: row, stroke: '#dce6df'});
      text(left - 9, row + 4, '$' + price, {'text-anchor': 'end'});
    }

    const maximumTicks = Math.max(2, Math.floor((right - left) / 75) + 1);
    const tickStep = Math.max(1, Math.ceil((last - first) / (maximumTicks - 1)));
    const months = [first];
    for (let month = first + tickStep; month <= last - tickStep; month += tickStep) months.push(month);
    if (last !== first) months.push(last);
    for (const month of months) {
      const col = x(month);
      svgElement(svg, 'line', {x1: col, x2: col, y1: top, y2: bottom, stroke: '#e7eeea'});
      text(col, bottom + 24, monthLabel(month), {'text-anchor': month === first ? 'start' : 'middle'});
    }

    const endLabels = [];
    for (const {name, color, points} of series) {
      const d = points.map(({month, price}, index) =>
        (index ? 'L' : 'M') + x(month).toFixed(2) + ',' + y(price).toFixed(2)
      ).join(' ');
      svgElement(svg, 'path', {
        d, fill: 'none', stroke: color, 'stroke-width': 3,
        'stroke-linecap': 'round', 'stroke-linejoin': 'round'
      });
      for (const {month, price} of points) {
        const dot = svgElement(svg, 'circle', {
          cx: x(month), cy: y(price), r: 4.5, fill: '#fff', stroke: color, 'stroke-width': 2
        });
        svgElement(dot, 'title', {}, name + ' · ' + monthLabel(month) + ' · ' + money.format(price) + '/g');
      }
      const latest = points[points.length - 1];
      if (latest.month === last) endLabels.push({color, price: latest.price, y: y(latest.price)});
    }

    endLabels.sort((a, b) => a.y - b.y);
    for (const [index, point] of endLabels.entries()) {
      const previous = endLabels[index - 1];
      const labelY = previous ? Math.max(point.y, previous.y + 16) : point.y;
      if (labelY !== point.y) {
        svgElement(svg, 'path', {
          d: 'M' + (right + 4) + ',' + point.y + 'L' + (right + 9) + ',' + labelY,
          fill: 'none', stroke: point.color
        });
      }
      text(right + 12, labelY + 4, money.format(point.price) + '/g', {
        fill: point.color, 'font-weight': 700
      });
    }
  }

  function buildChart(chart, points, host) {
    const series = chart.categories.map(([name, color]) => ({
      name, color,
      points: points.filter(point => point.category === name).sort((a, b) => a.month - b.month)
    })).filter(item => item.points.length);
    if (!series.length) return;

    const figure = document.createElement('figure');
    figure.className = 'market-price-chart';
    const caption = document.createElement('figcaption');
    caption.textContent = chart.title;
    figure.append(caption);

    if (series.length > 1) {
      const legend = document.createElement('ul');
      legend.className = 'market-chart-legend';
      for (const {name, color} of series) {
        const item = document.createElement('li');
        item.style.color = color;
        item.textContent = name;
        legend.append(item);
      }
      figure.append(legend);
    }

    const plot = document.createElement('div');
    figure.append(plot);
    host.append(figure);

    let previousWidth;
    const draw = () => {
      const width = Math.max(220, plot.clientWidth);
      if (width === previousWidth) return;
      previousWidth = width;
      renderPlot(plot, chart, series, width);
    };
    draw();
    const observer = new ResizeObserver(draw);
    observer.observe(plot);
  }

  async function start() {
    const response = await fetch('data/market-price-monthly.json', {cache: 'no-store'});
    if (!response.ok) throw Error('Pricing unavailable');
    const {observations = []} = await response.json();
    const points = observations
      .filter(point => /^\d{4}-(0[1-9]|1[0-2])$/.test(point.month) &&
        point.price_per_gram != null && point.price_per_gram !== '' &&
        Number.isFinite(Number(point.price_per_gram)) && Number(point.price_per_gram) >= 0)
      .map(point => ({
        category: point.category,
        month: monthIndex(point.month),
        price: Number(point.price_per_gram)
      }));

    const host = document.getElementById('history-chart');
    host.hidden = false;
    for (const chart of charts) buildChart(chart, points, host);
    if (!host.childElementCount) {
      host.hidden = true;
      throw Error('No prices');
    }
    document.getElementById('history-status').textContent = '';
  }

  start().catch(() => {
    document.getElementById('history-status').textContent = 'Price history temporarily unavailable.';
  });
})();
