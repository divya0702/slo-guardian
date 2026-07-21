export type Status = 'healthy' | 'warning' | 'breached' | 'insufficient_data'
export interface Node { id:string; label:string; traffic_class:string; status:Status; p99_ms:number }
export interface Evidence { id:string; kind:string; service:string; summary:string; value:number|string; unit?:string }
export interface Proposal { title:string; target?:{service:string;route:string;traffic_class:string}; action:{type:string;[key:string]:unknown}; ttl_seconds:number; evidence_ids:string[]; expected_effect:string }
export interface Candidate { policy_id:string; proposal:Proposal; state:string; rejection_reasons:string[] }
export interface Analysis { analysis_id:string; incident_id:string; packet:{scenario_id:string;service_graph:{nodes:Node[];edges:{source:string;target:string;traffic_class:string;retry_amplification:number}[]};slo_status:Record<string,{p99_ms:number;pressure:number;status:Status;retry_amplification:number;latency_budget_remaining_percent:number}>;evidence:Evidence[];recent_changes:{id:string;service:string;summary:string}[]};recommendation:{summary:string;suspected_root_cause:string;alternative_hypotheses:string[];risks:string[];uncertainty:string;confidence:number;evidence_ids:string[]};candidates:Candidate[] }
export interface Simulation { simulation_id:string;policy_id:string;mode:string;baseline:Metrics;projected:Metrics;observed?:Metrics;safe:boolean;rank_key:number[] }
export interface Metrics { checkout_p99_ms:number;critical_success_rate:number;critical_rejected:number;optional_degradation_percent:number;error_budget_consumption:number;retry_amplification:number }

