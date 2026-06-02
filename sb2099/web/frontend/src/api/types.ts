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
