async function generateForecast() {
    const weaverId = document.getElementById('weaverId').value;
    const targetMonth = document.getElementById('targetMonth').value;
    const language = document.getElementById('language').value;

    const loading = document.getElementById('loading');
    const recList = document.getElementById('recommendationsList');
    const buyerList = document.getElementById('buyerOpportunities');
    const activeMonthTag = document.getElementById('activeMonthTag');

    loading.style.display = 'block';
    recList.innerHTML = '';
    buyerList.innerHTML = '';
    activeMonthTag.innerText = targetMonth;

    try {
        const res = await fetch('/api/v1/forecast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                weaver_id: weaverId,
                target_month: targetMonth,
                language: language
            })
        });

        const data = await res.json();
        loading.style.display = 'none';

        // Render Recommendations
        data.recommendations.forEach(rec => {
            const card = document.createElement('div');
            card.className = 'rec-item';
            card.innerHTML = `
                <div class="rec-title-row">
                    <h3>${rec.item}</h3>
                    <span class="qty-badge">${rec.suggested_quantity} Units</span>
                </div>
                <div class="rec-meta">Target Completion: ${rec.target_date} | Predictive Confidence: ${Math.round(rec.confidence_score * 100)}%</div>
                <p style="font-size: 0.9rem; color: var(--text-heading); margin-bottom: 0.8rem;">${rec.rationale}</p>
                <button class="btn-voice" onclick="playVoicePrompt('${escapeQuotes(rec.voice_transcript)}', '${language}')">
                    <span>🔊</span> Listen Audio (${language})
                </button>
            `;
            recList.appendChild(card);
        });

        // Render Buyer Leads
        data.buyer_opportunities.forEach(opp => {
            const li = document.createElement('li');
            li.innerHTML = opp;
            buyerList.appendChild(li);
        });

    } catch (err) {
        loading.style.display = 'none';
        recList.innerHTML = `<p style="color: #ef4444;">Error connecting to FastAPI engine. Ensure backend is active.</p>`;
    }
}

function escapeQuotes(str) {
    return str.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function playVoicePrompt(text, language) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        
        if (language === 'Hindi') utterance.lang = 'hi-IN';
        else if (language === 'Odia') utterance.lang = 'hi-IN'; // Browser TTS fallback mapping for regional scripts
        else utterance.lang = 'en-US';

        window.speechSynthesis.speak(utterance);
    } else {
        alert("Voice synthesis is not supported on this browser.");
    }
}

// Auto-initialize on window load
window.onload = generateForecast;