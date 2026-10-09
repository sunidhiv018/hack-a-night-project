const express = require('express');
const path = require('path');

const app = express();
let PORT = process.env.PORT || 3001;

// Serve static assets from frontend directory and root assets
app.use(express.static(__dirname));
app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/assets', express.static(path.join(__dirname, '..', 'assets')));

// Routes
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'index.html'));
});

app.get('/login', (req, res) => {
  res.sendFile(path.join(__dirname, 'login.html'));
});

app.get('/dashboard', (req, res) => {
  res.sendFile(path.join(__dirname, 'dashboard.html'));
});

app.get('/transactions', (req, res) => {
  res.sendFile(path.join(__dirname, 'transactions.html'));
});

// Route aliases / placeholders
app.get('/forecasts', (req, res) => {
  res.sendFile(path.join(__dirname, 'forecasts.html'));
});

app.get('/savings', (req, res) => {
  res.sendFile(path.join(__dirname, 'savings.html'));
});

app.get('/time-machine', (req, res) => {
  res.sendFile(path.join(__dirname, 'time-machine.html'));
});

app.get('/reports', (req, res) => {
  res.sendFile(path.join(__dirname, 'reports.html'));
});

app.get('/import', (req, res) => {
  res.sendFile(path.join(__dirname, 'import.html'));
});

app.get('/chat', (req, res) => {
  res.sendFile(path.join(__dirname, 'chat.html'));
});

app.get('/milo', (req, res) => {
  res.sendFile(path.join(__dirname, 'chat.html'));
});



function startServer(port) {
  const server = app.listen(port, () => {
    console.log(`==================================================`);
    console.log(`🚀 BrokeNoMore Node.js Server running on port ${port}`);
    console.log(`👉 Access URL: http://localhost:${port}`);
    console.log(`==================================================`);
  });

  server.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`Port ${port} is busy, trying port ${port + 1}...`);
      startServer(port + 1);
    } else {
      console.error(err);
    }
  });
}

startServer(PORT);
