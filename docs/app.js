/* ==========================================================================
   PolitAgent - Frontend Application Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // Application State
    let sessionsData = [];
    let activeSessionId = null;

    // DOM Elements
    const searchInput = document.getElementById('search-input');
    const dateFilter = document.getElementById('date-filter');
    const sessionFilter = document.getElementById('session-filter');
    const sessionsList = document.getElementById('sessions-list');
    
    const welcomeView = document.getElementById('welcome-view');
    const protocolView = document.getElementById('protocol-view');
    const protocolContent = document.getElementById('protocol-content');
    const speakersContent = document.getElementById('speakers-content');
    const tabProtocol = document.getElementById('tab-protocol');
    const tabSpeakers = document.getElementById('tab-speakers');
    const externalYoutubeLink = document.getElementById('external-youtube-link');
    const backToListBtn = document.getElementById('back-to-list-btn');
    
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

    // Tab Switching
    if (tabProtocol && tabSpeakers) {
        tabProtocol.addEventListener('click', () => {
            tabProtocol.classList.add('active');
            tabSpeakers.classList.remove('active');
            protocolContent.classList.remove('hidden');
            speakersContent.classList.add('hidden');
        });

        tabSpeakers.addEventListener('click', () => {
            tabSpeakers.classList.add('active');
            tabProtocol.classList.remove('active');
            protocolContent.classList.add('hidden');
            speakersContent.classList.remove('hidden');
            
            // Render from cache
            const activeSession = sessionsData.find(s => s.id === activeSessionId);
            if (activeSession && activeSession.loadedSpeakersData) {
                renderSpeakerStatements(activeSession.loadedSpeakersData);
            }
        });
    }

    // Load Data
    const loadData = async () => {
        try {
            // Fetch the index json
            const response = await fetch('data/sessions.json');
            if (!response.ok) {
                throw new Error('Indexdatei sessions.json konnte nicht geladen werden.');
            }
            sessionsData = await response.json();
            
            // Populate stats and filters
            updateStats();
            populateFilters();
            
            // Render list
            renderSessionsList(sessionsData);
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
                // Remove active classes
                document.querySelectorAll('.session-card').forEach(c => c.classList.remove('active'));
                card.classList.add('active');
                
                // Load Protocol
                selectSession(session);
                
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
    const selectSession = async (session) => {
        activeSessionId = session.id;
        
        // Reset tabs to default (Protocol)
        if (tabProtocol && tabSpeakers) {
            tabProtocol.classList.add('active');
            tabSpeakers.classList.remove('active');
            tabSpeakers.disabled = true;
            tabSpeakers.setAttribute('title', 'Vergleicht Aussagen der Redner außerhalb des Plenums (z. B. auf Social Media, Webseiten, Abgeordnetenwatch).');
            protocolContent.classList.remove('hidden');
            if (speakersContent) speakersContent.classList.add('hidden');
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
            protocolView.classList.add('hidden');
            welcomeView.classList.remove('hidden');
            activeSessionId = null;
            document.querySelectorAll('.session-card').forEach(c => c.classList.remove('active'));
        });
    }

    // Initialize Page
    initTheme();
    loadData();
});
