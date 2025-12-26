// ============================================
// Audit Module - Aggregated Exports
// ============================================
// Central export point for all audit-related functionality

// API Client
export {
    fetchAuditStats,
    fetchSessionAuditLog,
    fetchAuditSessions,
    triggerAuditCleanup
} from './api.js';

// Panel UI
export {
    toggleAuditPanel,
    startAuditPolling,
    stopAuditPolling,
    loadCurrentSessionAudit,
    loadAuditStats,
    loadHistoricalSessions,
    handleAuditCleanup,
    initAuditPanel
} from './panel.js';
