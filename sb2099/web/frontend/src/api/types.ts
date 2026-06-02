export interface Tag { value: string; label: string; icon_url: string | null; sort: number }
export interface Submitter { nickname: string; avatar: string | null }
export interface Barrage {
  id: number; content: string; tags: string; cnt: number;
  submit_time: string | null; submitter?: Submitter | null
}
export interface BarragePage { list: Barrage[]; total: number; last_page: boolean }
export interface LiveItem {
  id: number; content_sample: string; send_cnt: number; unique_senders: number;
  last_seen: string | null; in_library: boolean; barrage_tags: string | null;
  first_sender?: { nickname: string; avatar: string | null } | null
}
export interface UserHit { uid: string; nickname: string; avatar: string | null }

// ---- admin ----------------------------------------------------------------
export interface AdminSettingItem {
  key: string; label: string; desc: string; kind: 'int' | 'lines';
  default: number | string[]; hint: string; value: number | string[] | null
}
export interface AdminTag {
  value: string; label: string; icon_url: string | null; sort: number;
  enabled: boolean; proposer_uid: string | null; proposer_nick: string | null;
  proposed_at: string | null; pending: { barrage_count: number; vote_count: number } | null
}
export interface AdminPendingItem {
  id: number; content: string; tags: string; submit_time: string | null; review_reason: string | null;
  submitter: { uid: string; nickname: string | null; avatar: string | null; last_seen: string | null } | null;
  recent_danmaku: { ts: string | null; content: string }[]
}
export interface AdminReportItem {
  id: number; content: string; tags: string; cnt: number; report_cnt: number;
  status: string; submit_time: string | null; last_report: string | null
}
export interface AdminTrashItem {
  id: number; content: string; tags: string; cnt: number; report_cnt: number; submit_time: string | null
}
export interface AdminBarrageItem {
  id: number; content: string; tags: string; cnt: number; report_cnt: number;
  submit_time: string | null; submitter: { nickname: string; avatar: string | null } | null
}
export interface AdminLiveHotItem {
  id: number; content_sample: string; live_date: string; send_cnt: number;
  unique_sender_cnt: number; last_seen: string | null; is_filtered: boolean
}
export interface AdminLiveHotDetail {
  hot: {
    id: number; live_date: string; content_norm: string; content_sample: string;
    send_cnt: number; unique_sender_cnt: number; first_seen: string | null;
    last_seen: string | null; is_filtered: boolean
  };
  raws: { uid: string | null; nickname: string | null; ts: string | null; content: string }[];
  top_uids: { uid: string; count: number }[]
}
export interface AdminStats {
  raw_24h: number; submit_24h: number; copy_total: number; live_hot_total: number;
  pending_total: number; deleted_total: number; report_24h: number;
  top_ip: { ip_hash: string; count: number }[]
}
