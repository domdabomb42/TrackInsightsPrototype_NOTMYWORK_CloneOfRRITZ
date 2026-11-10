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
      ? 'Time (minutes:seconds above 1 minute)'
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
    const percentileIndex = (value) => {
      if (distribution.bin_start === null || !distribution.bin_width) return null;
      const offset = distribution.has_underflow ? 1 : 0;
      return (Number(value) - distribution.bin_start) / distribution.bin_width - 0.5 + offset;
    };
    const percentileMarkers = {
      id: 'percentileMarkers',
      afterDatasetsDraw(chart) {
        const {ctx, chartArea, scales} = chart;
        if (!chartArea) return;
        ctx.save();
        (chartData.percentiles || []).forEach((percentile) => {
          const index = percentileIndex(percentile.value);
          if (index === null) return;
          const x = scales.x.getPixelForValue(index);
          if (x < chartArea.left || x > chartArea.right) return;
          const isMedian = percentile.label === '50th';
          ctx.strokeStyle = isMedian ? '#8c0327' : 'rgba(140, 3, 39, 0.55)';
          ctx.lineWidth = isMedian ? 2 : 1.5;
          ctx.setLineDash(isMedian ? [] : [5, 4]);
          ctx.beginPath();
          ctx.moveTo(x, chartArea.top);
          ctx.lineTo(x, chartArea.bottom);
          ctx.stroke();
          ctx.setLineDash([]);
        });
        ctx.restore();
      },
    };
    new Chart(distributionCanvas, {
      type: 'line',
      data: {
        labels: distribution.labels,
        datasets: [{
          label: 'Athletes',
          data: distribution.counts,
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
            ticks: { maxRotation: 45, minRotation: 0, autoSkip: true, maxTicksLimit: 10 },
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
