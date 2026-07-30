// Chart defaults for dark theme
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = 'Tajawal';
Chart.defaults.scale.grid.color = 'rgba(255, 255, 255, 0.05)';

// Setup Charts
const ctxCpu = document.getElementById('cpuChart').getContext('2d');
const ctxRam = document.getElementById('ramChart').getContext('2d');
const ctxTraffic = document.getElementById('trafficChart').getContext('2d');

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
    scales: {
        x: { display: false },
        y: { min: 0, max: 100, display: false }
    },
    elements: {
        point: { radius: 0, hitRadius: 10, hoverRadius: 4 }
    }
};

const cpuChart = new Chart(ctxCpu, {
    type: 'line',
    data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.2)', borderWidth: 2, fill: true, tension: 0.4 }] },
    options: commonOptions
});

const ramChart = new Chart(ctxRam, {
    type: 'line',
    data: { labels: Array(20).fill(''), datasets: [{ data: Array(20).fill(0), borderColor: '#8b5cf6', backgroundColor: 'rgba(139, 92, 246, 0.2)', borderWidth: 2, fill: true, tension: 0.4 }] },
    options: commonOptions
});

const trafficChart = new Chart(ctxTraffic, {
    type: 'line',
    data: {
        labels: Array(20).fill(''),
        datasets: [
            { label: 'الرسائل', data: Array(20).fill(0), borderColor: '#ec4899', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 },
            { label: 'المكالمات', data: Array(20).fill(0), borderColor: '#10b981', backgroundColor: 'transparent', borderWidth: 2, tension: 0.4 }
        ]
    },
    options: {
        ...commonOptions,
        scales: {
            x: { display: true, grid: { display: false } },
            y: { display: true, beginAtZero: true } // Let Y scale adjust dynamically if needed, but start at 0
        },
        plugins: { legend: { display: true, position: 'top', align: 'end' } }
    }
});

// WebSocket Connection
let wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
// تم تعديل الرابط ليتوافق مع المسار الجديد /ws/stats
let wsUrl = `${wsProtocol}//${window.location.host}/ws/stats`;
let ws;
let reconnectTimer;

function connectWebSocket() {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log("Dashboard WebSocket Connected");
        document.querySelector('.fa-globe').classList.add('text-green-400');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateDashboard(data);
    };

    ws.onclose = () => {
        console.log("WebSocket Disconnected. Reconnecting...");
        document.querySelector('.fa-globe').classList.remove('text-green-400');
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
        ws.close();
    }
}

function updateChartData(chart, newValue) {
    const data = chart.data.datasets[0].data;
    data.push(newValue);
    data.shift();
    chart.update('none');
}

function updateTrafficChart(chart, msgs, calls) {
    chart.data.datasets[0].data.push(msgs);
    chart.data.datasets[0].data.shift();
    chart.data.datasets[1].data.push(calls);
    chart.data.datasets[1].data.shift();
    
    const now = new Date();
    const timeStr = `${now.getHours()}:${now.getMinutes()}:${now.getSeconds()}`;
    chart.data.labels.push(timeStr);
    chart.data.labels.shift();
    
    chart.update('none');
}

function updateDashboard(data) {
    // تحديث المستخدمين
    if(data.users) {
        document.getElementById('stat-total-users').innerText = data.users.total;
        document.getElementById('stat-active-users').innerText = data.users.active;
    }
    
    // تحديث النشاط
    if(data.activity) {
        document.getElementById('stat-messages').innerText = data.activity.messages_per_sec;
        document.getElementById('stat-calls').innerText = data.activity.active_calls;
        updateTrafficChart(trafficChart, data.activity.messages_per_sec, data.activity.active_calls);
    }

    // تحديث النظام (قيم حقيقية)
    if(data.system) {
        document.getElementById('server-uptime').innerText = `مدة التشغيل: ${data.system.uptime}`;
        
        const cpu = data.system.cpu_percent;
        document.getElementById('cpu-text').innerText = `${cpu}%`;
        document.getElementById('cpu-bar').style.width = `${cpu}%`;
        updateChartData(cpuChart, cpu);
        
        const ram = data.system.ram_percent;
        document.getElementById('ram-text').innerText = `${ram}%`;
        document.getElementById('ram-bar').style.width = `${ram}%`;
        document.getElementById('ram-details').innerText = `${data.system.ram_used_gb} / ${data.system.ram_total_gb} GB`;
        updateChartData(ramChart, ram);
        
        const disk = data.system.disk_percent;
        document.getElementById('disk-text').innerText = `${disk}%`;
        const diskBar = document.getElementById('disk-bar');
        diskBar.style.width = `${disk}%`;
        
        if (disk > 90) diskBar.className = "bg-red-500 h-2.5 rounded-full transition-all";
        else if (disk > 70) diskBar.className = "bg-yellow-500 h-2.5 rounded-full transition-all";
        else diskBar.className = "bg-emerald-500 h-2.5 rounded-full transition-all";
    }

    // تحديث السجلات
    if(data.logs) {
        const logsContainer = document.getElementById('logs-container');
        
        if(data.logs.length === 0) {
            logsContainer.innerHTML = '<div class="text-center text-slate-500 mt-10">لا توجد أحداث حتى الآن</div>';
            return;
        }

        const newHtml = data.logs.map(log => {
            let icon = 'fa-info-circle text-blue-400';
            let bg = 'bg-blue-500/10 border-blue-500/20';
            
            if(log.action.includes('error')) { icon = 'fa-triangle-exclamation text-red-400'; bg = 'bg-red-500/10 border-red-500/20'; }
            if(log.action.includes('create')) { icon = 'fa-user-plus text-green-400'; bg = 'bg-green-500/10 border-green-500/20'; }
            if(log.action.includes('login')) { icon = 'fa-right-to-bracket text-purple-400'; bg = 'bg-purple-500/10 border-purple-500/20'; }

            return `
            <div class="log-item p-3 mb-2 rounded-lg border ${bg} flex items-start gap-3">
                <i class="fa-solid ${icon} mt-1"></i>
                <div class="flex-1">
                    <p class="text-sm text-slate-200">${log.details || log.action}</p>
                    <p class="text-xs text-slate-500 mt-1">${log.time}</p>
                </div>
            </div>`;
        }).join('');
        
        logsContainer.innerHTML = newHtml;
    }
}

// Init
connectWebSocket();
