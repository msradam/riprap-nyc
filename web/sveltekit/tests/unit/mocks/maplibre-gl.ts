/** Stub maplibre-gl for unit tests — happy-dom has no canvas / WebGL
 *  so the real module crashes constructing a Map. The page test
 *  doesn't assert on map rendering; it only needs the constructor
 *  to not throw and the method chain to be safely callable.
 *
 *  Every Map method RipMap.svelte calls is stubbed to a no-op so
 *  the component mounts to completion. Add new no-ops here as
 *  RipMap's method usage expands. */
class Map {
  constructor(_opts: unknown) {}
  on(_event: string, _fn?: (e: unknown) => void) { return this; }
  off(_event: string, _fn?: (e: unknown) => void) { return this; }
  once(_event: string, _fn?: (e: unknown) => void) { return this; }
  addSource() {}
  addLayer() {}
  removeLayer() {}
  removeSource() {}
  getSource() { return undefined; }
  getLayer() { return undefined; }
  setLayoutProperty() {}
  setPaintProperty() {}
  setFilter() {}
  fitBounds() {}
  setCenter() {}
  setZoom() {}
  getZoom() { return 15; }
  getCenter() { return { lng: 0, lat: 0 }; }
  addControl(_c: unknown) { return this; }
  removeControl(_c: unknown) { return this; }
  setMaxBounds() { return this; }
  setMinZoom() { return this; }
  setMaxZoom() { return this; }
  setLayerZoomRange() {}
  loadImage(_url: string, cb: (err: Error | null, img: unknown) => void) { cb(null, {}); }
  addImage() {}
  hasImage() { return true; }
  setStyle() {}
  remove() {}
  loaded() { return true; }
  isStyleLoaded() { return true; }
  flyTo() {}
  resize() {}
  queryRenderedFeatures() { return []; }
  project(_p: unknown) { return { x: 0, y: 0 }; }
  unproject(_p: unknown) { return { lng: 0, lat: 0 }; }
}
class NavigationControl {}
class ScaleControl {}
class AttributionControl {}
class Popup { setLngLat() { return this; } setHTML() { return this; } addTo() { return this; } remove() {} }
class Marker { setLngLat() { return this; } addTo() { return this; } remove() {} }
class LngLatBounds { extend() { return this; } }
export default {
  Map, NavigationControl, ScaleControl, AttributionControl,
  Popup, Marker, LngLatBounds,
};
export {
  Map, NavigationControl, ScaleControl, AttributionControl,
  Popup, Marker, LngLatBounds,
};
