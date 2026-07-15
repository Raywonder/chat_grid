export type AudioLayerState = {
  voice: boolean;
  item: boolean;
  media: boolean;
  world: boolean;
};

export type AnnouncementMode = 'full' | 'sounds_only' | 'required_only';

export type AudioAnnouncementSettings = {
  mode: AnnouncementMode;
  itemBeacons: boolean;
};
