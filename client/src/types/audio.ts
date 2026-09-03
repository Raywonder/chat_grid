export type AudioLayerState = {
  voice: boolean;
  item: boolean;
  media: boolean;
  world: boolean;
};

export type AnnouncementMode = 'full' | 'sounds_only' | 'required_only';
export type MediaAnnouncementMode = 'full' | 'sounds_only' | 'off';
export type RadioAnnouncementMode = MediaAnnouncementMode;

export type AudioAnnouncementSettings = {
  mode: AnnouncementMode;
  radioAnnouncementMode: RadioAnnouncementMode;
  tvAnnouncementMode: MediaAnnouncementMode;
  itemBeacons: boolean;
  movementDirections: boolean;
};
