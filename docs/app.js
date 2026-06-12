/* ==========================================================================
   PolitAgent - Frontend Application Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Application State
    let sessionsData = [];
    let activeSessionId = null;
    let pendingTabId = null;

    // DOM Elements
    const searchInput = document.getElementById('search-input');
    const dateFilter = document.getElementById('date-filter');
    const sessionFilter = document.getElementById('session-filter');
    const sessionsList = document.getElementById('sessions-list');
    
    const welcomeView = document.getElementById('welcome-view');
    const protocolView = document.getElementById('protocol-view');
    const protocolContent = document.getElementById('protocol-content');
    const speakersContent = document.getElementById('speakers-content');
    const documentsContent = document.getElementById('documents-content');
    const tabProtocol = document.getElementById('tab-protocol');
    const tabSpeakers = document.getElementById('tab-speakers');
    const tabDocuments = document.getElementById('tab-documents');
    const externalYoutubeLink = document.getElementById('external-youtube-link');
    const backToListBtn = document.getElementById('back-to-list-btn');
    const shareBtn = document.getElementById('share-btn');
    
    const statSessions = document.getElementById('stat-sessions');
    const statDays = document.getElementById('stat-days');
    
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const sidebar = document.querySelector('.sidebar');

    // Theme Management (Persist in LocalStorage)
    const initTheme = () => {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'light') {
            document.body.classList.remove('dark-mode');
            document.body.classList.add('light-mode');
        } else {
            document.body.classList.add('dark-mode');
            document.body.classList.remove('light-mode');
        }
    };

    darkModeToggle.addEventListener('click', () => {
        if (document.body.classList.contains('dark-mode')) {
            document.body.classList.remove('dark-mode');
            document.body.classList.add('light-mode');
            localStorage.setItem('theme', 'light');
        } else {
            document.body.classList.remove('light-mode');
            document.body.classList.add('dark-mode');
            localStorage.setItem('theme', 'dark');
        }
    });

    // Mobile Sidebar Toggle
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
        });
    }

    // Close mobile sidebar when clicking outside or selecting a card
    document.addEventListener('click', (e) => {
        if (window.innerWidth <= 900) {
            if (!sidebar.contains(e.target) && !mobileMenuBtn.contains(e.target) && sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('mobile-open');
            }
        }
    });

    // Central Tab Switching & Hash Updater
    const activateTab = (tabId) => {
        if (!tabProtocol || !tabSpeakers || !tabDocuments) return;

        // Reset all UI tab states
        tabProtocol.classList.remove('active');
        tabSpeakers.classList.remove('active');
        tabDocuments.classList.remove('active');
        
        protocolContent.classList.add('hidden');
        if (speakersContent) speakersContent.classList.add('hidden');
        if (documentsContent) documentsContent.classList.add('hidden');

        // Activate requested tab
        if (tabId === 'protocol') {
            tabProtocol.classList.add('active');
            protocolContent.classList.remove('hidden');
        } else if (tabId === 'speakers' && !tabSpeakers.disabled) {
            tabSpeakers.classList.add('active');
            if (speakersContent) speakersContent.classList.remove('hidden');
            
            // Render from cache
            const activeSession = sessionsData.find(s => s.id === activeSessionId);
            if (activeSession && activeSession.loadedSpeakersData) {
                renderSpeakerStatements(activeSession.loadedSpeakersData);
            }
        } else if (tabId === 'documents' && !tabDocuments.disabled) {
            tabDocuments.classList.add('active');
            if (documentsContent) documentsContent.classList.remove('hidden');
            
            // Render from cache
            const activeSession = sessionsData.find(s => s.id === activeSessionId);
            if (activeSession && activeSession.loadedDocumentsData) {
                renderDocumentsData(activeSession.loadedDocumentsData);
            }
        }

        // Update URL hash
        if (activeSessionId) {
            const targetHash = `#/session/${activeSessionId}/tab/${tabId}`;
            if (window.location.hash !== targetHash) {
                window.location.hash = targetHash;
            }
        }
    };

    // Tab Switching
    if (tabProtocol && tabSpeakers && tabDocuments) {
        tabProtocol.addEventListener('click', () => activateTab('protocol'));
        tabSpeakers.addEventListener('click', () => activateTab('speakers'));
        tabDocuments.addEventListener('click', () => activateTab('documents'));
    }

    // Load Data
    const loadData = async () => {
        try {
            // Fetch the index json (bypass HTTP cache to ensure we get the latest sessions)
            const response = await fetch('data/sessions.json', { cache: 'no-cache' });
            if (!response.ok) {
                throw new Error('Indexdatei sessions.json konnte nicht geladen werden.');
            }
            sessionsData = await response.json();
            
            // Populate stats and filters
            updateStats();
            populateFilters();
            
            // Render list
            renderSessionsList(sessionsData);
            
            // Initial routing check
            await handleRouting();
        } catch (error) {
            console.error('Fehler beim Laden der Sitzungsdaten:', error);
            renderErrorState(error.message);
        }
    };

    // Calculate & Update Dashboard Stats
    const updateStats = () => {
        if (statSessions) statSessions.textContent = sessionsData.length;
        
        // Count unique dates
        const uniqueDates = [...new Set(sessionsData.map(s => s.date).filter(d => d && d !== 'N/A'))];
        if (statDays) statDays.textContent = uniqueDates.length;
    };

    // Populate drop-down filters dynamically
    const populateFilters = () => {
        // Date options
        const uniqueDates = [...new Set(sessionsData.map(s => s.date).filter(d => d && d !== 'N/A'))].sort().reverse();
        uniqueDates.forEach(date => {
            const option = document.createElement('option');
            option.value = date;
            option.textContent = formatDateString(date);
            dateFilter.appendChild(option);
        });

        // Session numbers
        const uniqueSessions = [...new Set(sessionsData.map(s => s.session).filter(num => num && num > 0))].sort((a,b) => b-a);
        uniqueSessions.forEach(sess => {
            const option = document.createElement('option');
            option.value = sess;
            option.textContent = `${sess}. Sitzung`;
            sessionFilter.appendChild(option);
        });
    };

    // Helper to format YYYY-MM-DD to DD.MM.YYYY
    const formatDateString = (dateStr) => {
        if (!dateStr || dateStr === 'N/A') return 'Unbekannt';
        try {
            const parts = dateStr.split('-');
            if (parts.length === 3) {
                return `${parts[2]}.${parts[1]}.${parts[0]}`;
            }
            return dateStr;
        } catch {
            return dateStr;
        }
    };

    // Render list of sessions
    const renderSessionsList = (data) => {
        sessionsList.innerHTML = '';
        
        if (data.length === 0) {
            sessionsList.innerHTML = `
                <div class="empty-state">
                    <i class="fa-solid fa-folder-open"></i>
                    <p>Keine Sitzungen gefunden, die den Filtern entsprechen.</p>
                </div>
            `;
            return;
        }

        data.forEach(session => {
            const card = document.createElement('div');
            card.className = `session-card ${activeSessionId === session.id ? 'active' : ''}`;
            card.dataset.id = session.id;
            
            card.innerHTML = `
                <div class="card-top">
                    <span class="session-badge">${session.session > 0 ? `${session.session}. Sitzung` : 'Sondersitzung'}</span>
                    <span class="date-badge">${formatDateString(session.date)}</span>
                </div>
                <h3 class="card-title">${session.topic || session.title}</h3>
                <div class="card-footer">
                    <span class="top-indicator">TOP ${session.top || 'N/A'}</span>
                    <span><i class="fa-solid fa-chevron-right"></i></span>
                </div>
            `;

            card.addEventListener('click', () => {
                // Update hash to trigger router
                window.location.hash = `#/session/${session.id}/tab/protocol`;
                
                // Close sidebar on mobile after selection
                if (window.innerWidth <= 900) {
                    sidebar.classList.remove('mobile-open');
                }
            });

            sessionsList.appendChild(card);
        });
    };

    // Show Error State
    const renderErrorState = (msg) => {
        sessionsList.innerHTML = `
            <div class="error-state">
                <i class="fa-solid fa-circle-exclamation"></i>
                <p>Fehler beim Laden:</p>
                <small>${msg}</small>
            </div>
        `;
    };

    // Select and load a Bundestag session
    const selectSession = async (session, targetTabId = 'protocol') => {
        activeSessionId = session.id;
        pendingTabId = targetTabId;
        
        // Reset tabs to default (Protocol)
        if (tabProtocol && tabSpeakers && tabDocuments) {
            tabProtocol.classList.add('active');
            tabSpeakers.classList.remove('active');
            tabDocuments.classList.remove('active');
            tabSpeakers.disabled = true;
            tabDocuments.disabled = true;
            tabSpeakers.setAttribute('title', 'Vergleicht Aussagen der Redner außerhalb des Plenums (z. B. auf Social Media, Webseiten, Abgeordnetenwatch).');
            tabDocuments.setAttribute('title', 'Zeigt offizielle Bundestags-Drucksachen und Abstimmungsergebnisse.');
            protocolContent.classList.remove('hidden');
            if (speakersContent) speakersContent.classList.add('hidden');
            if (documentsContent) documentsContent.classList.add('hidden');
        }

        // Show loading spinner in content panel
        protocolView.classList.remove('hidden');
        welcomeView.classList.add('hidden');
        protocolContent.innerHTML = `
            <div class="loading-state">
                <i class="fa-solid fa-circle-notch fa-spin"></i>
                <p>Lade Protokoll aus '${session.summary_path}'...</p>
            </div>
        `;
        externalYoutubeLink.href = session.youtube_url;

        try {
            const response = await fetch(session.summary_path);
            if (!response.ok) {
                throw new Error(`Protokolldatei unter '${session.summary_path}' konnte nicht gelesen werden.`);
            }
            const markdownText = await response.text();
            
            // Configure Marked.js options
            marked.setOptions({
                gfm: true,
                breaks: true,
                headerIds: true
            });

            // Parse and set content
            let htmlContent = marked.parse(markdownText);
            protocolContent.innerHTML = htmlContent;
            
            // Clean up scrambled Gemini timestamps using the absolute ground truth of the video URL 't=' seconds parameter.
            // This prevents Gemini from shifting timestamps to the left (e.g., writing '04:10:00' for a 4m 10s video segment).
            const timelineLinks = protocolContent.querySelectorAll('a');
            timelineLinks.forEach(link => {
                const href = link.getAttribute('href');
                if (href && (href.includes('&t=') || href.includes('?t='))) {
                    const match = href.match(/[&?]t=(\d+)/);
                    if (match) {
                        const totalSeconds = parseInt(match[1], 10);
                        const hours = Math.floor(totalSeconds / 3600);
                        const minutes = Math.floor((totalSeconds % 3600) / 60);
                        const seconds = totalSeconds % 60;
                        
                        let formattedTime = '';
                        if (hours > 0) {
                            formattedTime = `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                        } else {
                            formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                        }
                        
                        // Only replace if the text matches a timestamp format (digits and colons)
                        const originalText = link.textContent.trim();
                        if (/^\d+(:\d+)+$/.test(originalText)) {
                            link.textContent = formattedTime;
                        }
                    }
                }
            });
            
            // Scroll reader back to top
            protocolContent.scrollTop = 0;

            // Fetch speakers statements if available
            if (session.speakers_path) {
                fetchSpeakersData(session);
            }

            // Fetch documents and voting data if available
            if (session.documents_path) {
                fetchDocumentsData(session);
            }
            
        } catch (error) {
            console.error(error);
            protocolContent.innerHTML = `
                <div class="error-state">
                    <i class="fa-solid fa-circle-xmark"></i>
                    <h2>Protokoll-Ladefehler</h2>
                    <p>${error.message}</p>
                </div>
            `;
        }
    };

    // Helper to get normalized party class
    const getPartyClass = (party) => {
        if (!party) return 'party-fraktionslos';
        const p = party.toLowerCase();
        if (p.includes('spd')) return 'party-spd';
        if (p.includes('cdu') || p.includes('csu')) return 'party-cdu-csu';
        if (p.includes('grün') || p.includes('grune')) return 'party-gruene';
        if (p.includes('fdp')) return 'party-fdp';
        if (p.includes('afd')) return 'party-afd';
        if (p.includes('linke')) return 'party-linke';
        if (p.includes('bsw')) return 'party-bsw';
        return 'party-fraktionslos';
    };

    // Helper to map platform to FontAwesome icon
    const getPlatformIcon = (platform) => {
        if (!platform) return 'fa-solid fa-link';
        const pl = platform.toLowerCase();
        if (pl.includes('abgeordnetenwatch')) return 'fa-solid fa-circle-question';
        if (pl.includes('social') || pl.includes('media') || pl.includes('twitter') || pl.includes('x') || pl.includes('instagram')) return 'fa-brands fa-x-twitter';
        if (pl.includes('presse') || pl.includes('news')) return 'fa-solid fa-newspaper';
        return 'fa-solid fa-globe';
    };

    // Fetch speaker statements from JSON
    const fetchSpeakersData = async (session) => {
        try {
            // If already cached, reuse
            if (session.loadedSpeakersData) {
                if (tabSpeakers && activeSessionId === session.id) {
                    tabSpeakers.disabled = false;
                    tabSpeakers.setAttribute('title', 'Vergleicht Aussagen der Redner außerhalb des Plenums (z. B. auf Social Media, Webseiten, Abgeordnetenwatch).');
                    if (pendingTabId === 'speakers') {
                        activateTab('speakers');
                        pendingTabId = null;
                    }
                }
                return;
            }

            const response = await fetch(session.speakers_path);
            if (!response.ok) {
                throw new Error("Fehler beim Laden der Abgeordneten-Stimmen.");
            }
            const data = await response.json();
            
            const hasRealUrl = (url) => {
                if (!url || url === 'N/A' || !url.startsWith('http')) return false;
                try {
                    const parsed = new URL(url);
                    return parsed.pathname !== '' && parsed.pathname !== '/';
                } catch (e) {
                    return false;
                }
            };
            
            const hasValidSpeakers = data.sources && data.sources.some(src => src.found && hasRealUrl(src.url));
            
            if (hasValidSpeakers) {
                session.loadedSpeakersData = data;
                if (tabSpeakers && activeSessionId === session.id) {
                    tabSpeakers.disabled = false;
                    tabSpeakers.setAttribute('title', 'Vergleicht Aussagen der Redner außerhalb des Plenums (z. B. auf Social Media, Webseiten, Abgeordnetenwatch).');
                    if (pendingTabId === 'speakers') {
                        activateTab('speakers');
                        pendingTabId = null;
                    }
                }
            } else {
                if (tabSpeakers && activeSessionId === session.id) {
                    tabSpeakers.disabled = true;
                    tabSpeakers.setAttribute('title', 'Keine spezifischen Abgeordneten-Stimmen mit Direkt-Links gefunden.');
                }
            }
        } catch (error) {
            console.warn('Konnte Abgeordneten-Stimmen nicht laden:', error);
            if (tabSpeakers && activeSessionId === session.id) {
                tabSpeakers.disabled = true;
            }
        }
    };

    // Render speaker statements tab contents
    const renderSpeakerStatements = (speakersData) => {
        if (!speakersContent) return;
        
        speakersContent.innerHTML = '';
        
        // Render synthesis
        const synthesisDiv = document.createElement('div');
        synthesisDiv.className = 'speakers-synthesis';
        synthesisDiv.innerHTML = `
            <h3><i class="fa-solid fa-circle-info"></i> Synthese der Positionen</h3>
            <p>${speakersData.synthesis || 'Keine Synthese verfügbar.'}</p>
        `;
        speakersContent.appendChild(synthesisDiv);
        
        // Render grid of cards
        const gridDiv = document.createElement('div');
        gridDiv.className = 'speakers-grid';
        
        const hasRealUrl = (url) => {
            if (!url || url === 'N/A' || !url.startsWith('http')) return false;
            try {
                const parsed = new URL(url);
                return parsed.pathname !== '' && parsed.pathname !== '/';
            } catch (e) {
                return false;
            }
        };

        const filteredSources = (speakersData.sources || []).filter(src => src.found && hasRealUrl(src.url));
        
        filteredSources.forEach(src => {
            const card = document.createElement('div');
            card.className = `speaker-card ${getPartyClass(src.party)}`;
            
            const iconClass = getPlatformIcon(src.platform);
            
            card.innerHTML = `
                <div class="speaker-header">
                    <div>
                        <h4 class="speaker-name">${src.name}</h4>
                        <span class="speaker-party">${src.party || 'Fraktionslos'}</span>
                    </div>
                </div>
                <div class="speaker-body">
                    <p class="speaker-quote">„${src.statement}“</p>
                </div>
                <div class="speaker-footer">
                    <a href="${src.url}" target="_blank" class="speaker-source-btn">
                        <i class="${iconClass}"></i> ${src.source_title || 'Zum Beitrag'}
                    </a>
                </div>
            `;
            gridDiv.appendChild(card);
        });
        
        speakersContent.appendChild(gridDiv);
        
        // Scroll back to top
        speakersContent.scrollTop = 0;
    };

    // Filter and search logic
    const filterAndSearch = () => {
        const query = searchInput.value.toLowerCase().trim();
        const selectedDate = dateFilter.value;
        const selectedSession = sessionFilter.value;

        const filtered = sessionsData.filter(session => {
            // Search Query check (title, topic, session number, top)
            const matchesQuery = !query || 
                session.title.toLowerCase().includes(query) ||
                (session.topic && session.topic.toLowerCase().includes(query)) ||
                (session.top && session.top.toLowerCase().includes(query)) ||
                String(session.session).includes(query);

            // Date filter check
            const matchesDate = !selectedDate || session.date === selectedDate;

            // Session filter check
            const matchesSession = !selectedSession || String(session.session) === selectedSession;

            return matchesQuery && matchesDate && matchesSession;
        });

        renderSessionsList(filtered);
    };

    // Events for filters
    searchInput.addEventListener('input', filterAndSearch);
    dateFilter.addEventListener('change', filterAndSearch);
    sessionFilter.addEventListener('change', filterAndSearch);

    // Mobile back button inside protocol viewer
    if (backToListBtn) {
        backToListBtn.addEventListener('click', () => {
            window.location.hash = '';
        });
    }

    // Fetch documents and voting data from JSON
    const fetchDocumentsData = async (session) => {
        try {
            // If already cached, reuse
            if (session.loadedDocumentsData) {
                if (tabDocuments && activeSessionId === session.id) {
                    tabDocuments.disabled = false;
                    tabDocuments.setAttribute('title', 'Zeigt offizielle Bundestags-Drucksachen und Abstimmungsergebnisse.');
                    if (pendingTabId === 'documents') {
                        activateTab('documents');
                        pendingTabId = null;
                    }
                }
                return;
            }

            const response = await fetch(session.documents_path);
            if (!response.ok) {
                throw new Error("Fehler beim Laden der Dokumenten-Daten.");
            }
            const data = await response.json();
            
            session.loadedDocumentsData = data;
            if (tabDocuments && activeSessionId === session.id) {
                tabDocuments.disabled = false;
                tabDocuments.setAttribute('title', 'Zeigt offizielle Bundestags-Drucksachen und Abstimmungsergebnisse.');
                if (pendingTabId === 'documents') {
                    activateTab('documents');
                    pendingTabId = null;
                }
            }
        } catch (error) {
            console.warn('Konnte Dokumenten-Daten nicht laden:', error);
            if (tabDocuments && activeSessionId === session.id) {
                tabDocuments.disabled = true;
                tabDocuments.setAttribute('title', 'Keine Dokumenten-Daten für diese Sitzung vorhanden.');
            }
        }
    };

    // Render documents and voting tab contents
    const renderDocumentsData = (docData) => {
        if (!documentsContent) return;
        
        documentsContent.innerHTML = '';
        
        // 1. Documents Section
        const docsSection = document.createElement('div');
        docsSection.className = 'documents-section';
        
        const docsHeader = document.createElement('h3');
        docsHeader.innerHTML = `<i class="fa-solid fa-file-pdf"></i> Offizielle Bundestags-Drucksachen`;
        docsSection.appendChild(docsHeader);
        
        const docs = docData.documents || [];
        if (docs.length === 0) {
            const emptyDocs = document.createElement('p');
            emptyDocs.className = 'empty-documents';
            emptyDocs.textContent = 'Für diese Debatte wurden keine spezifischen Drucksachen erfasst.';
            docsSection.appendChild(emptyDocs);
        } else {
            const gridDiv = document.createElement('div');
            gridDiv.className = 'documents-grid';
            
            docs.forEach(doc => {
                const card = document.createElement('div');
                card.className = 'document-card';
                
                let targetUrl = doc.url;
                if (targetUrl && targetUrl.includes('dip.bundestag.de/suche')) {
                    try {
                        const urlObj = new URL(targetUrl);
                        const term = urlObj.searchParams.get('term') || urlObj.searchParams.get('q') || '';
                        if (term) {
                            targetUrl = `https://dip.bundestag.de/suche?term=${encodeURIComponent(term)}&rows=25`;
                        }
                    } catch (e) {
                        console.warn('Fehler beim Formatieren der DIP-URL:', e);
                    }
                }
                
                const hasUrl = targetUrl && targetUrl !== 'N/A';
                
                card.innerHTML = `
                    <div class="document-badge">${doc.type || 'Drucksache'}</div>
                    <h4 class="document-title">${doc.title || 'Ohne Titel'}</h4>
                    <span class="document-number">${doc.number || 'Drucksache'}</span>
                    <div class="document-actions">
                        ${hasUrl ? `
                            <a href="${targetUrl}" target="_blank" class="document-download-btn">
                                <i class="fa-solid fa-file-arrow-down"></i> PDF / Suche anzeigen
                            </a>
                        ` : `
                            <button class="document-download-btn" disabled>
                                <i class="fa-solid fa-ban"></i> Nicht verfügbar
                            </button>
                        `}
                    </div>
                `;
                gridDiv.appendChild(card);
            });
            docsSection.appendChild(gridDiv);
        }
        documentsContent.appendChild(docsSection);
        
        // 2. Voting / Decision Section
        const votingSection = document.createElement('div');
        votingSection.className = 'voting-section';
        
        const votingHeader = document.createElement('h3');
        votingHeader.innerHTML = `<i class="fa-solid fa-box-archive"></i> Abstimmung & Beschluss`;
        votingSection.appendChild(votingHeader);
        
        const voting = docData.voting || {};
        
        if (voting.has_namentliche_abstimmung) {
            const votingCard = document.createElement('div');
            votingCard.className = 'voting-card';
            
            // Determine badge for outcome
            const isApproved = (voting.decision_text || '').toLowerCase().includes('angenommen');
            const resultBadgeClass = isApproved ? 'badge-approved' : 'badge-rejected';
            const resultBadgeText = isApproved ? 'Angenommen' : 'Abgelehnt';
            
            const overall = voting.overall_result || { ja: 0, nein: 0, enthaltung: 0, nicht_abgegeben: 0 };
            const jaVal = parseInt(overall.ja) || 0;
            const neinVal = parseInt(overall.nein) || 0;
            const enthVal = parseInt(overall.enthaltung) || 0;
            const totalVal = jaVal + neinVal + enthVal;
            
            // Percentages
            const jaPct = totalVal > 0 ? ((jaVal / totalVal) * 100).toFixed(1) : 0;
            const neinPct = totalVal > 0 ? ((neinVal / totalVal) * 100).toFixed(1) : 0;
            const enthPct = totalVal > 0 ? ((enthVal / totalVal) * 100).toFixed(1) : 0;
            
            votingCard.innerHTML = `
                <div class="voting-card-header">
                    <span class="voting-badge ${resultBadgeClass}">Namentliche Abstimmung: ${resultBadgeText}</span>
                    <p class="decision-desc">${voting.decision_text || ''}</p>
                </div>
                
                <div class="voting-visualization">
                    <h4>Gesamtergebnis</h4>
                    <div class="vote-bar">
                        ${jaVal > 0 ? `<div class="vote-part ja" style="width: ${jaPct}%" title="Ja: ${jaVal} (${jaPct}%)"></div>` : ''}
                        ${neinVal > 0 ? `<div class="vote-part nein" style="width: ${neinPct}%" title="Nein: ${neinVal} (${neinPct}%)"></div>` : ''}
                        ${enthVal > 0 ? `<div class="vote-part enthaltung" style="width: ${enthPct}%" title="Enthaltung: ${enthVal} (${enthPct}%)"></div>` : ''}
                    </div>
                    
                    <div class="vote-legend">
                        <span class="legend-item ja"><i class="fa-solid fa-circle"></i> Ja: <strong>${jaVal}</strong> (${jaPct}%)</span>
                        <span class="legend-item nein"><i class="fa-solid fa-circle"></i> Nein: <strong>${neinVal}</strong> (${neinPct}%)</span>
                        <span class="legend-item enthaltung"><i class="fa-solid fa-circle"></i> Enthaltung: <strong>${enthVal}</strong> (${enthPct}%)</span>
                    </div>
                </div>
                
                <div class="faction-breakdown">
                    <h4>Abstimmungsverhalten nach Fraktionen</h4>
                    <div class="factions-grid">
                        ${(voting.faction_results || [])
                            .filter(f => {
                                const fJa = parseInt(f.ja) || 0;
                                const fNein = parseInt(f.nein) || 0;
                                const fEnth = parseInt(f.enthaltung) || 0;
                                const fNa = parseInt(f.nicht_abgegeben) || 0;
                                return (fJa + fNein + fEnth + fNa) > 0;
                            })
                            .map(f => {
                                const fJa = parseInt(f.ja) || 0;
                                const fNein = parseInt(f.nein) || 0;
                                const fEnth = parseInt(f.enthaltung) || 0;
                                const fTotal = fJa + fNein + fEnth;
                                const fJaPct = fTotal > 0 ? ((fJa / fTotal) * 100).toFixed(0) : 0;
                                const fNeinPct = fTotal > 0 ? ((fNein / fTotal) * 100).toFixed(0) : 0;
                                const fEnthPct = fTotal > 0 ? ((fEnth / fTotal) * 100).toFixed(0) : 0;
                                
                                return `
                                    <div class="faction-vote-card ${getPartyClass(f.faction)}">
                                        <div class="faction-vote-header">
                                            <h5>${f.faction}</h5>
                                        </div>
                                        <div class="faction-vote-body">
                                            <div class="faction-vote-stats">
                                                <span class="f-stat ja">Ja: <strong>${fJa}</strong></span>
                                                <span class="f-stat nein">Nein: <strong>${fNein}</strong></span>
                                                <span class="f-stat enth">Enth.: <strong>${fEnth}</strong></span>
                                            </div>
                                            <div class="vote-bar small-bar">
                                                ${fJa > 0 ? `<div class="vote-part ja" style="width: ${fJaPct}%" title="Ja: ${fJaPct}%"></div>` : ''}
                                                ${fNein > 0 ? `<div class="vote-part nein" style="width: ${fNeinPct}%" title="Nein: ${fNeinPct}%"></div>` : ''}
                                                ${fEnth > 0 ? `<div class="vote-part enthaltung" style="width: ${fEnthPct}%" title="Enth.: ${fEnthPct}%"></div>` : ''}
                                            </div>
                                        </div>
                                    </div>
                                `;
                            }).join('')}
                    </div>
                </div>
                
                ${voting.official_voting_url && voting.official_voting_url !== 'N/A' ? `
                    <div class="voting-card-footer">
                        <a href="${voting.official_voting_url}" target="_blank" class="voting-link-btn">
                            <i class="fa-solid fa-circle-info"></i> Detailliertes Einzelergebnis auf bundestag.de
                        </a>
                    </div>
                ` : ''}
            `;
            votingSection.appendChild(votingCard);
        } else {
            // General decision text only
            const decisionCard = document.createElement('div');
            decisionCard.className = 'decision-card';
            decisionCard.innerHTML = `
                <div class="decision-badge">Normales Verfahren / Beschluss</div>
                <p class="decision-desc-text">${voting.decision_text || 'Es wurde kein spezifischer Beschluss aufgezeichnet.'}</p>
            `;
            votingSection.appendChild(decisionCard);
        }
        
        documentsContent.appendChild(votingSection);
        
        // Scroll back to top
        documentsContent.scrollTop = 0;
    };

    // Parse the hash URL
    const parseHash = () => {
        const hash = window.location.hash;
        // Format: #/session/{sessionId} or #/session/{sessionId}/tab/{tabId}
        const match = hash.match(/^#\/session\/([a-zA-Z0-9_-]+)(?:\/tab\/([a-z]+))?$/);
        if (match) {
            return {
                sessionId: match[1],
                tabId: match[2] || 'protocol'
            };
        }
        return null;
    };

    // Main Router
    const handleRouting = async () => {
        const route = parseHash();
        if (!route) {
            // No route or invalid, show welcome screen
            if (activeSessionId !== null) {
                activeSessionId = null;
                welcomeView.classList.add('hidden');
                protocolView.classList.add('hidden');
                welcomeView.classList.remove('hidden');
                document.querySelectorAll('.session-card').forEach(c => c.classList.remove('active'));
            }
            return;
        }

        const session = sessionsData.find(s => s.id === route.sessionId);
        if (!session) {
            console.warn(`Sitzung mit ID ${route.sessionId} nicht gefunden.`);
            return;
        }

        // Highlight active session card
        document.querySelectorAll('.session-card').forEach(c => {
            if (c.dataset.id === session.id) {
                c.classList.add('active');
                c.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            } else {
                c.classList.remove('active');
            }
        });

        // Load session if not active
        if (activeSessionId !== session.id) {
            await selectSession(session, route.tabId);
        } else {
            // Switch tab directly if not already active
            const tabButton = document.getElementById(`tab-${route.tabId}`);
            if (tabButton && !tabButton.classList.contains('active')) {
                activateTab(route.tabId);
            }
        }
    };

    // Wire up hashchange event listener
    window.addEventListener('hashchange', handleRouting);

    // Share Button click listener
    if (shareBtn) {
        shareBtn.addEventListener('click', async () => {
            const shareUrl = window.location.href;
            const activeSession = sessionsData.find(s => s.id === activeSessionId);
            
            let shareTitle = 'PolitAgent';
            let shareText = 'Sachliche Analysen & Protokolle der Bundestagssitzungen';
            
            if (activeSession) {
                const sessionNum = activeSession.session > 0 ? `${activeSession.session}. Sitzung` : 'Sitzung';
                const topStr = activeSession.top ? `TOP ${activeSession.top}` : '';
                const details = [sessionNum, topStr].filter(Boolean).join(', ');
                
                shareTitle = activeSession.topic || activeSession.title;
                shareText = `${shareTitle} (${details})`;
            }
            
            // Try Web Share API first (Mobile)
            if (navigator.share) {
                try {
                    await navigator.share({
                        title: shareTitle,
                        text: shareText,
                        url: shareUrl
                    });
                    console.log('Erfolgreich geteilt.');
                } catch (err) {
                    console.log('Teilen abgebrochen oder fehlgeschlagen:', err);
                }
            } else {
                // Clipboard fallback (Desktop)
                try {
                    await navigator.clipboard.writeText(shareUrl);
                    
                    // Visual feedback
                    const originalHTML = shareBtn.innerHTML;
                    shareBtn.innerHTML = `<i class="fa-solid fa-check" style="color: #10b981;"></i> Link kopiert!`;
                    shareBtn.style.borderColor = '#10b981';
                    
                    setTimeout(() => {
                        shareBtn.innerHTML = originalHTML;
                        shareBtn.style.borderColor = '';
                    }, 2000);
                } catch (err) {
                    console.error('Konnte Link nicht kopieren:', err);
                    alert('Link konnte nicht in die Zwischenablage kopiert werden.');
                }
            }
        });
    }

    // Initialize OneSignal Push Notifications
    const initOneSignal = async () => {
        try {
            const response = await fetch('data/config.json');
            if (!response.ok) return;
            const config = await response.json();
            if (!config.onesignal_app_id) return;

            const pushBtn = document.getElementById('push-notification-btn');
            if (!pushBtn) return;

            // Show push button
            pushBtn.classList.remove('hidden');

            const isGitHubPages = window.location.hostname.includes('github.io');
            const swPath = isGitHubPages ? 'PolitAgent/sw.js' : 'sw.js';
            const swScope = isGitHubPages ? '/PolitAgent/' : './';

            window.OneSignalDeferred = window.OneSignalDeferred || [];
            OneSignalDeferred.push(async function(OneSignal) {
                await OneSignal.init({
                    appId: config.onesignal_app_id,
                    serviceWorkerPath: swPath,
                    serviceWorkerParam: {
                        scope: swScope
                    }
                });

                // Helper to update button state
                const updateButtonState = (isSubscribed) => {
                    const icon = pushBtn.querySelector('i');
                    if (isSubscribed) {
                        pushBtn.classList.add('subscribed');
                        pushBtn.title = "Benachrichtigungen deaktivieren";
                        if (icon) {
                            icon.className = "fa-solid fa-bell";
                        }
                    } else {
                        pushBtn.classList.remove('subscribed');
                        pushBtn.title = "Benachrichtigungen aktivieren";
                        if (icon) {
                            icon.className = "fa-regular fa-bell";
                        }
                    }
                };

                // Check initial subscription status
                const isOptedIn = OneSignal.User.PushSubscription.optedIn;
                updateButtonState(isOptedIn);

                // Listen for changes
                OneSignal.User.PushSubscription.addEventListener("change", (event) => {
                    updateButtonState(event.current.optedIn);
                });

                // Toggle click handler
                pushBtn.addEventListener('click', async () => {
                    const currentOptedIn = OneSignal.User.PushSubscription.optedIn;
                    if (currentOptedIn) {
                        await OneSignal.User.PushSubscription.optOut();
                    } else {
                        await OneSignal.User.PushSubscription.optIn();
                    }
                });
            });
        } catch (err) {
            console.warn("OneSignal initialization skipped:", err);
        }
    };

    // Initialize GoatCounter Privacy-Friendly Analytics
    const initGoatCounter = async () => {
        try {
            const response = await fetch('data/config.json');
            if (!response.ok) return;
            const config = await response.json();
            if (!config.goatcounter_code) return;

            window.goatcounter = {
                no_onload: true
            };

            // Create script element
            const script = document.createElement('script');
            script.async = true;
            script.src = '//gc.zgo.at/count.js';
            script.dataset.goatcounter = `https://${config.goatcounter_code}.goatcounter.com/count`;
            document.head.appendChild(script);

            // Path generator helper
            const getPath = () => location.pathname + location.search + location.hash;

            // Track pageview function
            const trackPageview = () => {
                if (window.goatcounter && typeof window.goatcounter.count === 'function') {
                    window.goatcounter.count({
                        path: getPath()
                    });
                }
            };

            // Trigger on script load (initial pageview)
            script.onload = trackPageview;

            // Listen for SPA hash changes
            window.addEventListener('hashchange', trackPageview);
        } catch (err) {
            console.warn("GoatCounter initialization skipped:", err);
        }
    };

    // Register Service Worker for PWA support
    if ('serviceWorker' in navigator) {
        window.addEventListener('load', () => {
            navigator.serviceWorker.register('sw.js')
                .then(reg => {
                    console.log('Service Worker registriert scope:', reg.scope);
                    // Check for updates on load
                    reg.update();
                })
                .catch(err => console.error('Service Worker Registrierungsfehler:', err));
        });

        // Reload the page when the active service worker changes (new version activated)
        let refreshing = false;
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            if (!refreshing) {
                refreshing = true;
                window.location.reload();
            }
        });
    }

    // Initialize Page
    initTheme();
    loadData();
    initOneSignal();
    initGoatCounter();
});
