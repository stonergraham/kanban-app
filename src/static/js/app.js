// Test API connection
fetch('/api/health')
    .then(response => response.json())
    .then(data => {
        document.getElementById('status').textContent = 
            `✓ API Status: ${data.message}`;
    })
    .catch(error => {
        document.getElementById('status').textContent = 
            `✗ API Error: ${error.message}`;
        document.getElementById('status').style.background = '#ffebee';
        document.getElementById('status').style.color = '#c62828';
    });
