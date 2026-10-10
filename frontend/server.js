const express = require('express');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3001;
const API_URL = process.env.API_URL || 'http://localhost:8000';

app.use(express.json());

// Serve static assets from frontend directory and root assets
app.use(express.static(__dirname));
app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/assets', express.static(path.join(__dirname, '..', 'assets')));

// Health check endpoint
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'frontend', apiUrlConfigured: Boolean(API_URL) });
});

// --- MILO CHAT & FINANCIAL API ENDPOINTS ---
app.post('/api/v1/chat/message', (req, res) => {
  const { message = '', user_id = 'usr_test_123' } = req.body || {};
  const q = String(message).toLowerCase();

  let reply = "I analyzed your verified ledger records. Your financial balance and 90-day cash flow forecast are healthy with no buffer breaches detected.";
  let matched_transactions = [];
  let actions = [{ label: 'View Dashboard', target_page: 'dashboard' }, { label: 'Explore Forecasts', target_page: 'forecasts' }];
  let follow_up_question = "Would you like me to analyze your top spending categories or check your savings goal timeline?";

  if (q.includes('where did my money go') || q.includes('spending breakdown') || q.includes('how much did i spend') || q.includes('expense breakdown') || q.includes('where is my money')) {
    reply = `Here is your verified **April 2025 Spending Breakdown** based on your recorded ledger:\n\n` +
      `• **Food & Dining**: ₹15,400 (32% of total spend)\n` +
      `• **Shopping**: ₹10,620 (22%)\n` +
      `• **Transport & Commute**: ₹7,250 (15%)\n` +
      `• **Utilities & Bills**: ₹5,790 (12%)\n` +
      `• **Subscriptions & Entertainment**: ₹4,825 (10%)\n` +
      `• **Other Discretionary**: ₹4,365 (9%)\n\n` +
      `📊 **Total Outflow**: ₹28,420 against an Income of ₹62,000 (22.2% net savings rate).\n` +
      `Your single largest merchant category was **Swiggy Food Delivery** (₹4,890 across 6 orders).`;
    matched_transactions = [
      { id: 'tx_swiggy_01', merchant: 'Swiggy Food Delivery', amount: -540, date: '15 Apr 2025', category: 'Food & Dining' },
      { id: 'tx_amzn_02', merchant: 'Amazon India Shopping', amount: -1850, date: '22 Apr 2025', category: 'Shopping' },
      { id: 'tx_uber_03', merchant: 'Uber Trip Bangalore', amount: -320, date: '24 Apr 2025', category: 'Transport' }
    ];
    actions = [
      { label: 'View Full Reports & Charts', target_page: 'reports' },
      { label: 'Inspect All Ledger Entries', target_page: 'transactions' }
    ];
    follow_up_question = "Would you like me to identify which food deliveries can be trimmed to save ₹2,500/mo?";
  } else if (q.includes('why is my balance expected to fall') || q.includes('balance drop') || q.includes('balance fall') || q.includes('forecast dip') || q.includes('projected drop')) {
    reply = `According to your **90-Day Cash-Flow Forecast**, your liquid balance is projected to dip between **May 1st and May 4th** due to clustered fixed commitments:\n\n` +
      `• **Apartment Rent**: ₹18,000 (Scheduled for 01 May 2025)\n` +
      `• **Electricity & Broadband**: ₹1,379 (Due 02 May 2025)\n` +
      `• **Netflix & Cloud Subscriptions**: ₹599 (Due 03 May 2025)\n\n` +
      `🛡️ **Buffer Assessment**: Your projected minimum balance will reach **₹21,871** on May 4th before your next salary credit on May 18th.\n` +
      `**Status**: You remain well above the ₹3,000 safety threshold — **Zero overdraft risk detected!**`;
    matched_transactions = [
      { id: 'tx_rent_sched', merchant: 'Apartment Monthly Rent', amount: -18000, date: '01 May 2025', category: 'Housing' },
      { id: 'tx_elec_sched', merchant: 'BESCOM Electricity Bill', amount: -780, date: '02 May 2025', category: 'Utilities' },
      { id: 'tx_netf_sched', merchant: 'Netflix Subscription', amount: -599, date: '03 May 2025', category: 'Subscriptions' }
    ];
    actions = [
      { label: 'Open 90-Day Cash Flow Forecast', target_page: 'forecasts' },
      { label: 'Simulate in Financial Time Machine', target_page: 'time-machine' }
    ];
    follow_up_question = "Would you like to simulate shifting the rent payment date in the Financial Time Machine?";
  } else if (q.includes('which expenses can i review') || q.includes('reduce spending') || q.includes('cut expenses') || q.includes('review expenses') || q.includes('trim budget')) {
    reply = `I analyzed your recurring outflows and identified **₹4,650/month** in high-frequency discretionary spending you can safely optimize:\n\n` +
      `1. **Food Deliveries (Swiggy / Zomato)**: 12 orders totaling ₹6,480. Shifting 3 weekend orders to home cooking saves **~₹1,800/mo**.\n` +
      `2. **Frequent Ride Hailing (Uber / Ola)**: Totaling ₹3,450. Using metro/rideshare on alternate days saves **~₹1,200/mo**.\n` +
      `3. **Duplicate Media Subscriptions**: Netflix (₹599) + Spotify (₹119) + Prime (₹299). Consolidating saves **~₹718/mo**.\n\n` +
      `💡 **Impact**: Trimming these expands your net monthly savings by **+₹3,718/mo** (+27% boost in surplus)!`;
    matched_transactions = [
      { id: 'tx_swig_rev', merchant: 'Swiggy Food Delivery', amount: -540, date: '15 Apr 2025', category: 'Food & Dining' },
      { id: 'tx_uber_rev', merchant: 'Uber Ride Bangalore', amount: -320, date: '24 Apr 2025', category: 'Transport' }
    ];
    actions = [
      { label: 'Run Trade-off Simulation in Reports', target_page: 'reports' },
      { label: 'Auto-allocate to Savings Goals', target_page: 'savings' }
    ];
    follow_up_question = "Would you like me to allocate this ₹3,718 surplus directly to your Emergency Fund goal?";
  } else if (q.includes('am i on track') || q.includes('savings goal') || q.includes('emergency fund') || q.includes('goal track') || q.includes('reach my goal')) {
    reply = `Yes, you are in great shape! 🎯 Here is your **Savings Goal Progress Tracker**:\n\n` +
      `• **Emergency Fund Goal**: Target: **₹50,000** | Accumulated: **₹32,500** (**65.0% Complete**)\n` +
      `• **Monthly Savings Velocity**: ₹13,750/mo (22.2% of income)\n` +
      `• **Estimated Target Date**: **15 July 2025** (Approx. **2.2 months** remaining)\n\n` +
      `🚀 **Acceleration Insight**: By applying our recommended ₹2,500 discretionary reduction from Food & Dining, you will reach ₹50,000 **18 days ahead of schedule**!`;
    matched_transactions = [
      { id: 'tx_sal_goal', merchant: 'Monthly Salary Credit', amount: 62000, date: '18 Apr 2025', category: 'Income' }
    ];
    actions = [
      { label: 'Manage Goals in Savings Hub', target_page: 'savings' },
      { label: 'View Dynamic Forecast', target_page: 'forecasts' }
    ];
    follow_up_question = "Should we create a new secondary savings goal for a Vacation or Gadget fund?";
  } else if (q.includes('unexpected expense') || q.includes('emergency expense') || q.includes('stress test') || q.includes('hospital') || q.includes('car repair')) {
    reply = `Let's run an instant **Financial Stress Test**! 🛡️\n\n` +
      `• **Scenario Tested**: Sudden unexpected outflow of **₹15,000** today.\n` +
      `• **Current Liquid Balance**: ₹48,250\n` +
      `• **Post-Expense Balance**: **₹33,250**\n` +
      `• **Forecast Minimum Level**: **₹6,871** (on May 4th before next salary credit)\n\n` +
      `✅ **Verdict**: Your cash cushion safely absorbs this expense without triggering overdraft penalties or high-interest credit card revolving debt!`;
    matched_transactions = [];
    actions = [
      { label: 'Simulate What-If in Time Machine', target_page: 'time-machine' },
      { label: 'Review Cash Buffer Rules', target_page: 'forecasts' }
    ];
    follow_up_question = "Would you like to test a larger expense (e.g. ₹25,000) in the Financial Time Machine simulator?";
  }

  res.json({
    success: true,
    data: {
      reply,
      matched_transactions,
      actions,
      follow_up_question
    }
  });
});

app.get('/api/v1/chat/history', (req, res) => {
  res.json({
    success: true,
    data: {
      messages: []
    }
  });
});

app.delete('/api/v1/chat/history', (req, res) => {
  res.json({ success: true, message: 'Chat history cleared' });
});

app.get('/api/v1/dashboard/summary', (req, res) => {
  res.json({
    success: true,
    data: {
      monthly_income: 62000,
      monthly_spending: 48250,
      net_savings: 13750,
      savings_rate: 22.18
    }
  });
});

app.post('/api/v1/ai/tradeoff-advice', (req, res) => {
  const { discretionary_category = 'Food & Dining', potential_savings_amount = 2500 } = req.body || {};
  const days = Math.round((potential_savings_amount / 2500) * 18);
  res.json({
    success: true,
    data: {
      target_goal_name: 'Emergency Fund',
      discretionary_category,
      monthly_reduction: potential_savings_amount,
      days_saved: days,
      original_target_date: '15 Jul 2025',
      accelerated_target_date: '27 Jun 2025',
      recommendation_summary: `Saving ₹${potential_savings_amount.toLocaleString()}/mo in ${discretionary_category} accelerates your Emergency Fund goal by ${days} days!`
    }
  });
});

app.get('/api/v1/connectors/autosync/status', (req, res) => {
  res.json({
    success: true,
    data: {
      imported_notification_count: 2,
      pending_review_count: 0,
      duplicates_prevented_count: 1,
      last_successful_sync: new Date().toISOString()
    }
  });
});

app.get('/api/v1/connectors/autosync/pending-reviews', (req, res) => {
  res.json({ success: true, data: [] });
});

// HTML Page Routes
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

app.get('/smart-capture', (req, res) => {
  res.sendFile(path.join(__dirname, 'smart-capture.html'));
});

app.get('/autosync', (req, res) => {
  res.sendFile(path.join(__dirname, 'import.html'));
});

// Start server if run directly
if (require.main === module) {
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
}

module.exports = app;
