document.addEventListener('DOMContentLoaded', () => {
  const dataElement = document.getElementById('event-chart-data');
  if (!dataElement) {
    return;
  }

  const chartData = JSON.parse(dataElement.textContent || '{}');
  const isFieldEvent = chartData.eventType === 'Field';
  const axisTitle = isFieldEvent
    ? 'Distance (inches)'
    : chartData.distributionUsesMinutes
      ? 'Time (minutes)'
      : 'Time (seconds)';
  const trendAxisTitle = isFieldEvent
    ? 'Median distance (inches)'
    : 'Median time (seconds)';
  const markLabel = (value) => {
    if (isFieldEvent) {
      const inches = Number(value);
      const feet = Math.floor(inches / 12);
      const remainder = inches - feet * 12;
      return `${feet}'${remainder.toFixed(2).replace(/\.?0+$/, '')}"`;
    }

    const seconds = Number(value);
    if (seconds >= 60) {
      const minutes = Math.floor(seconds / 60);
      return `${minutes}:${(seconds - minutes * 60).toFixed(2).padStart(5, '0')}`;
    }
    return `${seconds.toFixed(2)}s`;
  };
  const distributionCanvas = document.getElementById('event-distribution-chart');
  const trendCanvas = document.getElementById('event-trend-chart');

  if (typeof Chart === 'undefined') {
    [distributionCanvas, trendCanvas].forEach((canvas) => {
      if (canvas) {
        canvas.parentElement.textContent = 'Charts could not load. Please refresh to try again.';
      }
    });
    return;
  }

  if (distributionCanvas && chartData.distribution.labels.length) {
    const distribution = chartData.distribution;
    const distributionLabels = chartData.lowerIsBetter
      ? [...distribution.labels].reverse()
      : distribution.labels;
    const distributionCounts = chartData.lowerIsBetter
      ? [...distribution.counts].reverse()
      : distribution.counts;
    const percentileIndex = (value) => {
      if (distribution.bin_start === null || !distribution.bin_width) return null;
      const offset = distribution.has_underflow ? 1 : 0;
      const index = (Number(value) - distribution.bin_start) / distribution.bin_width - 0.5 + offset;
      return chartData.lowerIsBetter ? distribution.labels.length - 1 - index : index;
    };
    const percentileMarkers = {
      id: 'percentileMarkers',
      afterDatasetsDraw(chart) {
        const {ctx, chartArea, scales} = chart;
        if (!chartArea) return;
        const markers = [];
        ctx.save();
        (chartData.percentiles || []).forEach((percentile) => {
          const index = percentileIndex(percentile.value);
          if (index === null) return;
          const x = scales.x.getPixelForValue(index);
          if (x < chartArea.left || x > chartArea.right) return;
          const isMedian = percentile.label === '50th';
          const color = isMedian ? '#8c0327' : 'rgba(140, 3, 39, 0.75)';
          ctx.strokeStyle = color;
          ctx.lineWidth = isMedian ? 2 : 1.5;
          ctx.setLineDash(isMedian ? [] : [5, 4]);
          ctx.beginPath();
          ctx.moveTo(x, chartArea.top);
          ctx.lineTo(x, chartArea.bottom);
          ctx.stroke();
          ctx.setLineDash([]);
          markers.push({x, label: `${percentile.label.slice(0, -2)}%`, color});
        });

        ctx.font = '600 9px Arial, sans-serif';
        const labelHeight = 12;
        markers.forEach((marker) => {
          const labelWidth = ctx.measureText(marker.label).width + 8;
          const left = Math.max(
            chartArea.left,
            Math.min(chartArea.right - labelWidth, marker.x - labelWidth / 2),
          );
          let lane = 0;
          while (markers.some((other) => {
            if (other === marker || other.lane !== lane || other.left === undefined) return false;
            return left < other.left + other.width + 3 && left + labelWidth + 3 > other.left;
          })) lane += 1;
          marker.left = left;
          marker.width = labelWidth;
          marker.lane = lane;

          const top = chartArea.top + 2 + lane * 12;
          ctx.fillStyle = 'rgba(255,255,255,.94)';
          ctx.fillRect(left, top, labelWidth, labelHeight);
          ctx.strokeStyle = marker.color;
          ctx.lineWidth = 1;
          ctx.strokeRect(left, top, labelWidth, labelHeight);
          ctx.fillStyle = '#8c0327';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(marker.label, left + labelWidth / 2, top + labelHeight / 2);
        });
        ctx.restore();
      },
    };
    new Chart(distributionCanvas, {
      type: 'line',
      data: {
        labels: distributionLabels,
        datasets: [{
          label: 'Athletes',
          data: distributionCounts,
          borderColor: '#8c0327',
          borderWidth: 2.5,
          backgroundColor: 'rgba(140, 3, 39, 0.14)',
          fill: true,
          tension: 0.45,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: '#8c0327',
        }],
      },
      plugins: [percentileMarkers],
      options: {
        maintainAspectRatio: false,
        layout: { padding: { top: 0 } },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => `${items[0].label}${isFieldEvent ? ' in' : ' sec'}`,
              label: (item) => `${item.formattedValue} athlete${Number(item.raw) === 1 ? '' : 's'}`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: axisTitle },
            grid: { display: false },
            ticks: { maxRotation: 0, minRotation: 0, autoSkip: true, maxTicksLimit: 10 },
          },
          y: {
            beginAtZero: true,
            ticks: { precision: 0 },
          },
        },
      },
    });
  }

  if (trendCanvas && chartData.trend.years.length) {
    const trendChart = new Chart(trendCanvas, {
      type: 'line',
      data: {
        labels: chartData.trend.years,
        datasets: chartData.trend.datasets.map((dataset) => ({
          ...dataset,
          pointRadius: 4,
          pointHoverRadius: 6,
          borderWidth: 2,
        })),
      },
      options: {
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (item) => `${item.dataset.label}: ${markLabel(item.raw)}`,
            },
          },
        },
        scales: {
          x: { title: { display: true, text: 'Season' } },
          y: {
            reverse: false,
            title: { display: true, text: trendAxisTitle },
            ticks: { callback: (value) => markLabel(value) },
          },
        },
      },
    });

    document.querySelectorAll('.event-trend-toggle').forEach((toggle) => {
      toggle.addEventListener('change', () => {
        const datasetIndex = trendChart.data.datasets.findIndex(
          (dataset) => dataset.label === toggle.dataset.trend,
        );
        if (datasetIndex === -1) {
          return;
        }

        trendChart.setDatasetVisibility(datasetIndex, toggle.checked);
        trendChart.update();
      });
    });
  }
});
