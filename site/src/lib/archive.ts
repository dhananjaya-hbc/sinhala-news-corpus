// Public-domain historical photographs of Ceylon used as illustrations.
// They never depict the day's news: every caption says "Archive photograph"
// and gives the year. Sources were checked as "Public domain" on Wikimedia
// Commons; see the About page for the full picture credits.
import type { CategoryId } from "./data";

export interface ArchivePhoto {
  id: string; // file name in public/archive/ (also <id>-sm.jpg at 720px)
  w: number;
  h: number;
  si: string; // Sinhala caption
  en: string; // English caption (original printed caption where there is one)
  year: string;
  credit: string;
  source: string; // Wikimedia Commons file page
}

const CAVE = "H.W. Cave & Co., Colombo · Bibliothèque nationale de France";
const cave = (page: number) =>
  `https://commons.wikimedia.org/wiki/File:Views_of_Colombo_and_Kandy,_Ceylon,_published_by_H.W._Cave_and_Co.,_Colombo._Album_de_24_phot._de_Ceylan_en_1901._Don_1930_-_btv1b53216130r_(${String(page).padStart(2, "0")}_of_30).jpg`;

export const ARCHIVE: ArchivePhoto[] = [
  { id: "queen-street-1907", w: 1400, h: 910, si: "ප්‍රදීපාගාරය පෙනෙන ක්වීන් වීදිය, කොළඹ", en: "Queen Street, showing the lighthouse, Colombo", year: "1907", credit: "Postcard · New York Public Library", source: "https://commons.wikimedia.org/wiki/File:Queen_Street,_showing_light_house,_Colombo_(NYPL_Hades-2359794-4044559).jpg" },
  { id: "tea-carts-1901", w: 1400, h: 847, si: "නැව්ගත කිරීමට ලංකා තේ තොටුපළට රැගෙන යාම", en: "Carting Ceylon tea to the wharf for shipment", year: "1901", credit: CAVE, source: cave(9) },
  { id: "ophir-colombo-harbour-1901", w: 1400, h: 827, si: "ඔෆීර් නෞකාව සහ සහාය නැව් කොළඹ වරායේ", en: "The Ophir and her convoy lying in Colombo harbour, with the Duke and Duchess of Cornwall and York on board, April 1901", year: "1901", credit: CAVE, source: cave(7) },
  { id: "galle-face-1901", w: 1400, h: 871, si: "කොළඹ ක්ලබය සහ ගාලු මුවදොර හෝටලය, ගාලු මුවදොර පිට්ටනිය", en: "The Colombo Club and the Galle Face Hotel", year: "1901", credit: CAVE, source: cave(13) },
  { id: "electric-tramway-1899", w: 942, h: 676, si: "ලංකාවේ පළමු විදුලි ට්‍රෑම් රථ සේවය", en: "“Western civilization in the East”: the first electric tramway in Ceylon. Drawing by Joseph Nash, The Graphic, 10 June 1899", year: "1899", credit: "The Graphic", source: "https://commons.wikimedia.org/wiki/File:Tramway1899.jpg" },
  { id: "kandy-perahera-1901", w: 1400, h: 1127, si: "මහනුවර ඇසළ පෙරහැර", en: "The Perahera, an annual Buddhist procession, Kandy", year: "1901", credit: "Postcard · New York Public Library", source: "https://commons.wikimedia.org/wiki/File:The_Perahera,_an_annual_Buddhist_procession._Kandy_(Ceylon)_(NYPL_Hades-2359856-4044621).jpg" },
  { id: "pettah-street-1901", w: 1400, h: 858, si: "පිටකොටුවේ වීදියක්", en: "A street in the Pettah", year: "1901", credit: CAVE, source: cave(11) },
  { id: "fishing-fleet-1901", w: 1400, h: 835, si: "කොළඹ වෙරළේ ධීවර ඔරු", en: "“This motley fleet is the first scene of novelty”: fishing boats at Colombo", year: "1901", credit: CAVE, source: cave(6) },
  { id: "colombo-breakwater-1901", w: 1400, h: 939, si: "කොළඹ දියකඩනයෙන් පිටත රළ", en: "Outside the Colombo breakwater", year: "1901", credit: CAVE, source: cave(4) },
  { id: "colombo-harbour-1901", w: 1400, h: 869, si: "කොළඹ දියකඩනය ඇතුළත, වරාය", en: "Inside the Colombo breakwater", year: "1901", credit: CAVE, source: cave(5) },
  { id: "grand-oriental-hotel-1901", w: 1400, h: 874, si: "ග්‍රෑන්ඩ් ඔරියන්ටල් හෝටලය, කොළඹ", en: "The Grand Oriental Hotel", year: "1901", credit: CAVE, source: cave(8) },
  { id: "fort-entrance-1901", w: 1400, h: 862, si: "ගාලු මුවදොර සිට කොටුවට පිවිසුම", en: "Entrance to the Fort from Galle Face", year: "1901", credit: CAVE, source: cave(12) },
  { id: "dalada-maligawa-1901", w: 1400, h: 843, si: "මහනුවර දළදා මාළිගාව", en: "The Dalada Maligawa at Kandy", year: "1901", credit: CAVE, source: cave(22) },
  { id: "matale-road-elephants-1901", w: 1400, h: 838, si: "අලි රංචුවක් නිසා අවහිර වූ මාතලේ පාර", en: "The Matale road blocked by elephants", year: "1901", credit: CAVE, source: cave(26) },
  { id: "weighing-tea", w: 1400, h: 1057, si: "තේ කිරීම, ලංකාව", en: "Weighing tea, Ceylon", year: "c. 1900s", credit: "Bain News Service · Library of Congress", source: "https://commons.wikimedia.org/wiki/File:Weighing_tea-_Ceylon_LCCN2014682548.jpg" },
];

const byId = new Map(ARCHIVE.map((p) => [p.id, p]));
const photo = (id: string) => byId.get(id)!;

/** The illustration at the head of each section front. */
export const SECTION_PHOTO: Record<CategoryId, ArchivePhoto> = {
  politics: photo("queen-street-1907"), // Queen Street, home of Queen's House (today President's House)
  business: photo("tea-carts-1901"),
  international: photo("ophir-colombo-harbour-1901"),
  sports: photo("galle-face-1901"),
  technology: photo("electric-tramway-1899"),
  entertainment: photo("kandy-perahera-1901"),
  local: photo("pettah-street-1901"),
  other: photo("fishing-fleet-1901"),
};

// Photos not used by a section come first, so the front page doesn't show
// the same picture twice in the first editions.
const sectionIds = new Set(Object.values(SECTION_PHOTO).map((p) => p.id));
const ROTATION = [...ARCHIVE.filter((p) => !sectionIds.has(p.id)), ...ARCHIVE.filter((p) => sectionIds.has(p.id))];

/** "From the archive" on the front page: a different photograph each edition. */
export function photoOfTheDay(edition: number): ArchivePhoto {
  return ROTATION[(Math.max(1, edition) - 1) % ROTATION.length];
}
