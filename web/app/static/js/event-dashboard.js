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
    new Chart(distributionCanvas, {
      type: 'bar',
      data: {
        labels: chartData.distribution.labels,
        datasets: [{
          label: 'Athlete-season bests',
          data: chartData.distribution.counts,
          backgroundColor: 'rgba(140, 3, 39, 0.68)',
          borderColor: '#8c0327',
          borderWidth: 1,
          borderRadius: 4,
        }],
      },
      options: {
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (items) => items[0].label,
              label: (item) => `${item.formattedValue} athlete-season bests`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: axisTitle },
            ticks: { maxRotation: 45, minRotation: 0, autoSkip: true, maxTicksLimit: 12 },
          },
          y: {
            beginAtZero: true,
            title: { display: true, text: 'Athlete-season count' },
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
