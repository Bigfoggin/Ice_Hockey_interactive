// Hockey verstehen – pitch deck (English), built as a structured, editable PowerPoint
const path = require('path');
const pptxgen = require('pptxgenjs');
const { applyTheme } = require(process.env.SKILL + '/scripts/apply_theme.js');

const IMG = process.env.IMG; // folder with screenshots
const HERE = __dirname;
const OUT = process.env.OUT;

const THEME = {
  name: 'Hockey verstehen',
  headFontFace: 'Montserrat',
  bodyFontFace: 'Montserrat',
  colors: {
    dk1: '001F3F', lt1: 'FFFFFF', dk2: '00142B', lt2: 'B8C7D9',
    accent1: '66C1D3', accent2: 'D7192D', accent3: '1D4ED8', accent4: '00284F', accent5: 'A9E3EE', accent6: 'F5B800',
    hlink: '66C1D3', folHlink: 'A9E3EE',
  },
};

const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5 in
pres.title = 'Hockey verstehen – Pitch';
pres.author = 'Hockey verstehen team';
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
const C = pres.SchemeColor;
const W = 13.333, M = 0.75;

const footer = (color) => [
  { text: { text: 'HOCKEY VERSTEHEN  ·  SPORT INNOVATION CHALLENGE 2026', options: { x: M, y: 6.95, w: 8, h: 0.3, fontSize: 9, bold: true, charSpacing: 2, color, margin: 0 } } },
];

pres.defineSlideMaster({
  title: 'Title',
  background: { path: path.join(HERE, 'bg-title.png') },
  objects: [
    { placeholder: { options: { name: 'eyebrow', type: 'body', align: 'left', x: M, y: 0.7, w: 11.8, h: 0.4, fontSize: 14, bold: true, charSpacing: 4, color: C.accent1, margin: 0 }, text: 'EYEBROW' } },
    { placeholder: { options: { name: 'title', type: 'title', align: 'left', x: M, y: 1.35, w: 11.8, h: 3.9, fontSize: 64, bold: true, color: C.background1, valign: 'top', margin: 0, lineSpacingMultiple: 0.9 }, text: 'Title' } },
    { placeholder: { options: { name: 'sub', type: 'body', align: 'left', x: M, y: 5.45, w: 9.5, h: 0.9, fontSize: 18, color: C.background2, valign: 'top', margin: 0 }, text: 'Subtitle' } },
    ...footer(C.background2),
  ],
});

const content = (name, bg, eyebrowColor, titleColor, footColor) => pres.defineSlideMaster({
  title: name,
  background: bg,
  margin: [0.5, M, 0.6, M],
  objects: [
    { placeholder: { options: { name: 'eyebrow', type: 'body', align: 'left', x: M, y: 0.55, w: 11.8, h: 0.35, fontSize: 13, bold: true, charSpacing: 4, color: eyebrowColor, margin: 0 }, text: 'SECTION' } },
    { placeholder: { options: { name: 'title', type: 'title', align: 'left', x: M, y: 0.95, w: 11.8, h: 1.45, fontSize: 40, bold: true, color: titleColor, valign: 'top', margin: 0, lineSpacingMultiple: 0.92 }, text: 'Title' } },
    ...footer(footColor),
  ],
  slideNumber: { x: 12.0, y: 6.95, w: 0.6, h: 0.3, fontSize: 9, bold: true, color: footColor, align: 'right' },
});
content('Content dark', { path: path.join(HERE, 'bg-dark.png') }, C.accent1, C.background1, C.background2);
content('Content light', { color: THEME.colors.accent1 }, C.text1, C.text1, C.text1);

// ---------- helpers ----------
const twoTone = (a, b, light) => [
  { text: a, options: { breakLine: true } },
  { text: b, options: { color: light ? C.text2 : C.accent1 } },
];
function card(s, x, y, w, h, name, fill = C.accent4) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.18, fill: { color: fill, transparency: 15 }, line: { color: C.accent1, width: 0.75, transparency: 70 }, objectName: name });
}
function ring(s, x, y, d, label, name, size = 22) {
  s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: C.accent4 }, line: { color: C.accent1, width: 2.5 }, objectName: name });
  s.addText(label, { x, y, w: d, h: d, align: 'center', valign: 'middle', fontSize: size, bold: true, color: C.accent1, margin: 0, isTextBox: true, objectName: name + ' label' });
}
function tagText(s, text, x, y, w, color = C.accent1) {
  s.addText(text.toUpperCase(), { x, y, w, h: 0.3, fontSize: 11, bold: true, charSpacing: 3, color, margin: 0, isTextBox: true });
}
function phone(s, img, x, y, h, name) {
  const w = h * 0.5;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: 0.3, fill: { color: '0B0B0B' }, line: { color: '333333', width: 1.5 }, objectName: name + ' frame', shadow: { type: 'outer', color: '66C1D3', blur: 18, offset: 4, angle: 90, opacity: 0.35 } });
  const p = 0.09, iw = w - 2 * p, ih = iw / 0.463;
  s.addImage({ path: img, x: x + p, y: y + p, w: iw, h: Math.min(ih, h - 2 * p), sizing: { type: 'crop', w: iw, h: Math.min(ih, h - 2 * p) }, altText: name, objectName: name });
}

// ---------- 1 Title ----------
pres.addSection({ title: 'Opening' });
let s = pres.addSlide({ masterName: 'Title', sectionTitle: 'Opening' });
s.addText('SPORT INNOVATION CHALLENGE 2026  ·  SPENGLER CUP DAVOS', { placeholder: 'eyebrow' });
s.addText(twoTone('BE A PRO.', 'OR LEARN THE GAME.'), { placeholder: 'title' });
s.addText('Two offers for two audiences, both powered by Wisehockey data: a pass game for fans and live rule explanations for newcomers.', { placeholder: 'sub' });
s.addNotes('We bring two offers to the Spengler Cup, for two different audiences. Be a Pro: a pass game for fans who want to play like a pro. Learn the Game: live explanations for newcomers, every time the referee blows the whistle. Both run on Wisehockey data.');

// ---------- 2 Problem and user need ----------
pres.addSection({ title: '1 Problem and user need' });
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '1 Problem and user need' });
s.addText('01  ·  PROBLEM AND USER NEED', { placeholder: 'eyebrow' });
s.addText(twoTone('TWO TARGET GROUPS.', 'BOTH CAN ONLY WATCH.'), { placeholder: 'title' });
const groups = [
  ['Be a Pro', 'The fan', 'Regular viewer, plays or follows hockey', '“I know where the pass should go. But I never get to make the call.”', 'Step into a pro’s shoes and compare with other fans and pros.'],
  ['Learn the Game', 'The newcomer', 'Family member, casual viewer, holiday guest in Davos', '“The referee blows the whistle and everyone reacts. I have no idea what just happened.”', 'Know instantly what was called and why, without jargon.'],
];
const gw = (W - 2 * M - 0.4) / 2;
groups.forEach(([offer, t, who, pain, need], i) => {
  const x = M + i * (gw + 0.4);
  card(s, x, 2.55, gw, 3.55, `Target group ${i + 1}`);
  ring(s, x + 0.35, 2.8, 0.75, String(i + 1), `Target group badge ${i + 1}`, 22);
  s.addText([{ text: offer.toUpperCase(), options: { fontSize: 20, bold: true, color: C.background1, breakLine: true } }, { text: t + ': ' + who.charAt(0).toLowerCase() + who.slice(1), options: { fontSize: 13, color: C.background2 } }], { x: x + 1.3, y: 2.78, w: gw - 1.6, h: 0.85, margin: 0, valign: 'middle', isTextBox: true });
  tagText(s, 'Problem', x + 0.35, 3.85, gw - 0.7);
  s.addText(pain, { x: x + 0.35, y: 4.15, w: gw - 0.7, h: 0.95, fontSize: 16, italic: true, color: C.accent1, margin: 0, valign: 'top', isTextBox: true });
  tagText(s, 'Need', x + 0.35, 5.05, gw - 0.7);
  s.addText(need, { x: x + 0.35, y: 5.35, w: gw - 0.7, h: 0.6, fontSize: 15, color: C.background1, margin: 0, valign: 'top', isTextBox: true });
});
s.addText([{ text: 'Problem statement: ', options: { bold: true, color: C.accent1 } }, { text: 'The Spengler Cup reaches millions, but its digital channels only let them watch. Fans cannot play, newcomers cannot follow.', options: { color: C.background1 } }], { x: M, y: 6.25, w: 11.8, h: 0.62, fontSize: 14, margin: 0, valign: 'top', isTextBox: true });
s.addNotes('Two target groups with two different problems. The fan knows where the pass should go, but never gets to make the call. The newcomer hears the whistle, sees everyone react, and has no idea what just happened. In both cases, the digital channels only let them watch. So we built one offer for each.');

// ---------- 3 Be a Pro ----------
pres.addSection({ title: '2 Concept and interaction' });
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '2 Concept and interaction' });
s.addText('02  ·  OFFER 1 · BE A PRO  ·  FOR FANS', { placeholder: 'eyebrow' });
s.addText(twoTone('PREDICT THE PASS.', 'PLAY LIKE A PRO.'), { placeholder: 'title' });
s.addImage({ path: path.join(IMG, 'passspiel-zone-entry.jpg'), x: M, y: 2.6, w: 6.0, h: 3.75, altText: 'Be a Pro prototype: prediction 2.5 m off, 83 points', objectName: 'Screenshot Be a Pro' });
s.addText('Be a Pro prototype: 2.5 m off = 83 points', { x: M, y: 6.45, w: 6, h: 0.25, fontSize: 10, color: C.background2, margin: 0, isTextBox: true });
const pro = [['When', 'In the intermission, with key scenes from the last period.'], ['Do', 'The scene freezes. You draw where the puck goes next.'], ['Score', 'The distance to the real pass gives your points: every metre counts.'], ['Learn', 'Why the real pass worked, e.g. Knuble finds Walsh in front of the net: 40 % goal chance.'], ['Shine', 'The top 10 appear on the video cube after the break.']];
pro.forEach(([h, d], i) => {
  ring(s, 7.2, 2.62 + i * 0.78, 0.52, String(i + 1), `Pro step ${i + 1}`, 15);
  s.addText([{ text: h.toUpperCase(), options: { fontSize: 12, bold: true, charSpacing: 2, color: C.accent1, breakLine: true } }, { text: d, options: { fontSize: 13, color: C.background1 } }], { x: 7.9, y: 2.56 + i * 0.78, w: 4.7, h: 0.75, margin: 0, valign: 'top', isTextBox: true });
});
s.addNotes('Offer one, Be a Pro, for fans. In the intermission, key scenes from the last period are ready. The scene freezes, you draw the pass, and the distance to the real pass is your score: 2.5 metres off gives 83 points. Then the app shows why the real pass worked, for example Knuble finding Walsh in front of the net, a 40 percent chance. After the break the top 10 appear on the video cube.');

// ---------- 4 Learn the Game ----------
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '2 Concept and interaction' });
s.addText('02  ·  OFFER 2 · LEARN THE GAME  ·  FOR NEWCOMERS', { placeholder: 'eyebrow' });
s.addText(twoTone('THE REFEREE WHISTLES.', 'YOU KNOW WHY.'), { placeholder: 'title' });
const flow = [['Whistle', 'The game is live. The referee stops play.'], ['Live data', 'Wisehockey reports the reason: icing, offside, penalty, goal.'], ['Explanation', 'Your phone shows instantly what was called and why, with the referee signal.']];
flow.forEach(([h, d], i) => {
  const y = 2.65 + i * 1.12;
  ring(s, M, y, 0.75, String(i + 1), `Learn step ${i + 1}`, 20);
  s.addText([{ text: h.toUpperCase(), options: { fontSize: 15, bold: true, color: C.background1, breakLine: true } }, { text: d, options: { fontSize: 14, color: C.background2 } }], { x: M + 1.0, y: y - 0.02, w: 5.2, h: 0.85, margin: 0, valign: 'middle', isTextBox: true });
  if (i < 2) s.addText('↓', { x: M + 0.15, y: y + 0.75, w: 0.45, h: 0.35, fontSize: 16, bold: true, color: C.accent1, align: 'center', margin: 0, isTextBox: true });
});
card(s, M, 5.95, 6.2, 0.75, 'Whistle fact');
s.addText([{ text: '60 stoppages in the final  ', options: { bold: true, color: C.accent1 } }, { text: '= 60 moments to learn, exactly when newcomers are confused.', options: { color: C.background1 } }], { x: M + 0.3, y: 6.0, w: 5.7, h: 0.65, fontSize: 14, margin: 0, valign: 'middle', isTextBox: true });
phone(s, path.join(IMG, 'app-watch.png'), 7.6, 2.4, 4.25, 'Screenshot icing explained');
phone(s, path.join(IMG, 'app-watch-pp.png'), 10.25, 2.4, 4.25, 'Screenshot penalty explained');
s.addText('Learn the Game prototype: icing and penalty explained', { x: 7.6, y: 6.75, w: 4.9, h: 0.25, fontSize: 10, color: C.background2, margin: 0, isTextBox: true });
s.addNotes('Offer two, Learn the Game, for newcomers. It runs live during the game. The referee blows the whistle, Wisehockey reports the reason, and the phone immediately shows what was called and why, with a short animation and the referee signal. In the final there were 60 stoppages of play, so 60 moments to learn, exactly when a newcomer is confused.');

// ---------- 5 Data and feasibility ----------
pres.addSection({ title: '3 Data, feasibility and impact' });
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '3 Data, feasibility and impact' });
s.addText('03  ·  USE OF DATA AND FEASIBILITY', { placeholder: 'eyebrow' });
s.addText(twoTone('ONE DATA SOURCE.', 'TWO EXPERIENCES.'), { placeholder: 'title' });
ring(s, W / 2 - 0.6, 2.55, 1.2, 'DATA', 'Data source', 16);
s.addText([{ text: 'WISEHOCKEY TRACKING', options: { fontSize: 14, bold: true, color: C.background1, breakLine: true } }, { text: 'Chip in the puck, tags on every player · 4,458 events in the final', options: { fontSize: 12, color: C.background2 } }], { x: W / 2 - 3, y: 3.85, w: 6, h: 0.65, align: 'center', margin: 0, isTextBox: true });
const uses = [['Be a Pro uses', ['Positions of all 12 players per event', 'Passes with start and target point', 'xG of the following shot']], ['Learn the Game uses', ['Stoppage reason: icing, offside, goal …', 'Penalty type and player', 'Game state: power play, empty net']]];
const cw2 = (W - 2 * M - 0.4) / 2;
uses.forEach(([h, items], i) => {
  const x = M + i * (cw2 + 0.4);
  card(s, x, 4.65, cw2, 1.95, `Data use ${i + 1}`);
  s.addText(h.toUpperCase(), { x: x + 0.3, y: 4.8, w: cw2 - 0.6, h: 0.3, fontSize: 13, bold: true, charSpacing: 2, color: C.accent1, margin: 0, isTextBox: true });
  s.addText(items.map((t, k) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: k < items.length - 1 } })), { x: x + 0.3, y: 5.15, w: cw2 - 0.6, h: 1.3, fontSize: 14, color: C.background1, paraSpaceAfter: 4, margin: 0, valign: 'top', isTextBox: true });
});
s.addText('Feasible today: both prototypes run on the real data of the 2025 final. Wisehockey delivers the same data for every game, live.', { x: M, y: 6.72, w: 11.8, h: 0.22, fontSize: 11, color: C.background2, margin: 0, isTextBox: true });
s.addNotes('Both offers run on one data source: Wisehockey tracking, with a chip in the puck and tags on every player. Be a Pro uses the positions of all players, the passes with start and target point, and the goal chance of the following shot. Learn the Game uses the stoppage reason, the penalty type and the game state. Both prototypes already run on the real data of the 2025 final, and Wisehockey delivers this live for every game.');

// ---------- 6 Why they return and how we measure success ----------
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '3 Data, feasibility and impact' });
s.addText('03  ·  WHY THEY RETURN AND HOW WE MEASURE IMPACT', { placeholder: 'eyebrow' });
s.addText(twoTone('EVERY GAME', 'IS A NEW REASON TO COME BACK.'), { placeholder: 'title' });
const loops = [['Be a Pro', 'New scenes in every intermission, 22 rounds per tournament, a ranking that keeps going.'], ['Learn the Game', 'Every whistle teaches something new. After a few games, newcomers follow on their own.']];
loops.forEach(([h, d], i) => {
  const y = 2.6 + i * 1.5;
  card(s, M, y, 5.6, 1.3, `Loop ${i + 1}`);
  s.addText([{ text: h.toUpperCase(), options: { fontSize: 14, bold: true, color: C.accent1, breakLine: true } }, { text: d, options: { fontSize: 14, color: C.background1 } }], { x: M + 0.3, y: y + 0.1, w: 5.0, h: 1.1, margin: 0, valign: 'middle', isTextBox: true });
});
s.addText('Baseline: Event Report 2025 (1.2 M visitors, 2.5 M page views, Key Player vote, newsletter). A pilot compares 2026 against it.', { x: M, y: 5.7, w: 5.6, h: 0.75, fontSize: 11, color: C.background2, margin: 0, valign: 'top', isTextBox: true });
const tx = 6.85, tw2 = W - M - tx;
card(s, tx, 2.55, tw2, 4.2, 'KPI table');
s.addText('HOW WE MEASURE SUCCESS', { x: tx + 0.3, y: 2.72, w: tw2 - 0.6, h: 0.3, fontSize: 12, bold: true, charSpacing: 2, color: C.accent1, margin: 0, isTextBox: true });
const head = { fontSize: 11, bold: true, color: C.background2, margin: 0, isTextBox: true };
s.addText('KPI', { ...head, x: tx + 0.3, y: 3.1, w: 1.9, h: 0.3 });
s.addText('BASELINE 2025', { ...head, x: tx + 2.2, y: 3.1, w: 1.55, h: 0.3 });
s.addText('EXPECTED EFFECT', { ...head, x: tx + 3.8, y: 3.1, w: tw2 - 4.05, h: 0.3 });
const kpi = [['Time on site', 'not reported', 'Intermissions and live play become active time'], ['Page views per visitor', '≈ 2.1', 'Scenes, replays and explanations'], ['Registrations', '3,210', 'The top 10 needs a name'], ['Newsletter clicks', '3–5 %', 'New scenes after every game']];
kpi.forEach(([k, b, e], i) => {
  const y = 3.5 + i * 0.75;
  s.addShape(pres.shapes.LINE, { x: tx + 0.3, y: y - 0.06, w: tw2 - 0.6, h: 0, line: { color: C.accent1, width: 0.5, transparency: 70 }, objectName: `KPI rule ${i + 1}` });
  s.addText(k, { x: tx + 0.3, y, w: 1.85, h: 0.6, fontSize: 14, bold: true, color: C.background1, margin: 0, valign: 'middle', isTextBox: true });
  s.addText(b, { x: tx + 2.2, y, w: 1.55, h: 0.6, fontSize: 14, bold: true, color: C.accent1, margin: 0, valign: 'middle', isTextBox: true });
  s.addText('↑  ' + e, { x: tx + 3.8, y, w: tw2 - 4.05, h: 0.6, fontSize: 12, color: C.background1, margin: 0, valign: 'middle', isTextBox: true });
});
s.addNotes('Why do people come back? For fans, every intermission is a new round and the ranking keeps going over all games. For newcomers, every whistle teaches something new, until they can follow on their own. The Spengler Cup reaches millions anyway, so we measure whether our offers move engagement: time on site, page views, registrations and newsletter clicks, against the 2025 baseline.');

// ---------- 7 Activation ----------
pres.addSection({ title: '4 Activation' });
s = pres.addSlide({ masterName: 'Content dark', sectionTitle: '4 Activation' });
s.addText('04  ·  WHERE IT LIVES  ·  LIGHTWEIGHT ACTIVATION', { placeholder: 'eyebrow' });
s.addText(twoTone('PART OF THE GAME.', 'ON EVERY CHANNEL.'), { placeholder: 'title' });
const act = [['Web', 'Both offers on spenglercup.ch, side by side. Newsletter (21,300 contacts) links to new scenes.'], ['Social media', 'Reels “Can you read this pass?” for Be a Pro, short rule clips for Learn the Game.'], ['Arena', 'Announcer and video cube: play now in the break, top 10 after it. QR code for live explanations.'], ['Streaming', 'QR code in the YouTube stream, rule of the day in “Spengler Cup Today”.']];
const aw = 3.85;
act.forEach(([h, d], i) => {
  const x = M + (i % 2) * (aw + 0.3), y = 2.6 + Math.floor(i / 2) * 1.85;
  card(s, x, y, aw, 1.65, `Channel ${i + 1}`);
  s.addText([{ text: h.toUpperCase(), options: { fontSize: 14, bold: true, color: C.accent1, breakLine: true } }, { text: d, options: { fontSize: 13, color: C.background1 } }], { x: x + 0.3, y: y + 0.12, w: aw - 0.55, h: 1.4, margin: 0, valign: 'middle', isTextBox: true });
});
s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 9.1, y: 2.75, w: 3.5, h: 2.8, rectRadius: 0.25, rotate: -3, fill: { color: C.accent1 }, line: { type: 'none' }, objectName: 'Ticket', shadow: { type: 'outer', color: '000000', blur: 20, offset: 6, angle: 90, opacity: 0.4 } });
s.addText([{ text: 'THE REWARD', options: { fontSize: 12, bold: true, charSpacing: 2, color: C.text1, breakLine: true } }, { text: 'SPENGLER CUP 2026 TICKETS', options: { fontSize: 22, bold: true, color: C.text1, breakLine: true } }, { text: 'for the best Be a Pro players of the tournament (symbolic)', options: { fontSize: 13, color: C.text1 } }], { x: 9.4, y: 2.95, w: 2.95, h: 2.4, rotate: -3, margin: 0, valign: 'middle', isTextBox: true, objectName: 'Ticket text' });
s.addText('Be a pro. Or learn the game. Either way, part of the game.', { x: 9.0, y: 5.95, w: 3.7, h: 0.6, fontSize: 14, italic: true, color: C.background2, margin: 0, isTextBox: true });
s.addNotes('Activation is lightweight because the channels already exist. Both offers sit side by side on spenglercup.ch and in the newsletter. On social media: pass reels and short rule clips. In the arena: the announcer and video cube, plus a QR code for live explanations. In the stream: a QR code and a rule of the day. The reward: tickets for next year. Be a pro, or learn the game. Either way, part of the game. Thank you.');

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log('written', OUT);
})();
