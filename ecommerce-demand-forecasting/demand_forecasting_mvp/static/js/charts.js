document.addEventListener('DOMContentLoaded', function () {
    // Get the charts context
    const forecastCtx = document.getElementById('forecastChart')?.getContext('2d');
    const categoriesCtx = document.getElementById('categoriesChart')?.getContext('2d');

    // Common chart options
    const commonOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                position: 'top',
                labels: {
                    padding: 20,
                    font: {
                        family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
                        size: 12
                    }
                }
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                padding: 12,
                titleFont: {
                    size: 14,
                    weight: 'bold'
                },
                bodyFont: {
                    size: 13
                },
                cornerRadius: 4
            }
        }
    };

    // Initialize Forecast Chart if it exists
    if (forecastCtx) {
        new Chart(forecastCtx, {
            type: 'line',
            data: {
                labels: forecastData.dates,
                datasets: [{
                    label: 'Actual Demand',
                    data: forecastData.actual,
                    borderColor: '#10a37f',
                    backgroundColor: 'rgba(16, 163, 127, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }, {
                    label: 'Predicted Demand',
                    data: forecastData.predicted,
                    borderColor: '#6e6e80',
                    borderDash: [5, 5],
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                }]
            },
            options: {
                ...commonOptions,
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.1)'
                        }
                    }
                }
            }
        });
    }

    // Initialize Categories Chart if it exists
    if (categoriesCtx) {
        new Chart(categoriesCtx, {
            type: 'doughnut',
            data: {
                labels: categoryData.labels,
                datasets: [{
                    data: categoryData.values,
                    backgroundColor: [
                        '#10a37f',
                        '#2563eb',
                        '#7c3aed',
                        '#db2777',
                        '#ea580c'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                ...commonOptions,
                cutout: '60%',
                plugins: {
                    ...commonOptions.plugins,
                    legend: {
                        ...commonOptions.plugins.legend,
                        position: 'right'
                    }
                }
            }
        });
    }

    // Handle dark mode changes
    const darkModeMediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const updateChartColors = (e) => {
        const isDark = e.matches;
        const gridColor = isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
        const textColor = isDark ? '#ffffff' : '#353740';

        Chart.instances.forEach(chart => {
            if (chart.config.type === 'line') {
                chart.options.scales.y.grid.color = gridColor;
                chart.options.scales.x.ticks.color = textColor;
                chart.options.scales.y.ticks.color = textColor;
            }
            chart.options.plugins.legend.labels.color = textColor;
            chart.update();
        });
    };

    darkModeMediaQuery.addListener(updateChartColors);
    updateChartColors(darkModeMediaQuery);
}); 