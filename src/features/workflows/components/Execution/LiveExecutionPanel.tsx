// Compatibility shim – re-export RealtimeExecutionPanel as LiveExecutionPanel
// This file exists so older imports of `LiveExecutionPanel` continue to work
// while the UI now uses `RealtimeExecutionPanel`.
import RealtimeExecutionPanel from './RealtimeExecutionPanel';
export default RealtimeExecutionPanel;
