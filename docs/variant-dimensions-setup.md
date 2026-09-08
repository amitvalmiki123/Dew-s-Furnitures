# PDP Dimensions / Material & Care — variant-aware metafield blocks

**Dew's Furniture · Shopify Dawn 16.0.0**

Ye guide batata hai ki Dimensions block ko kaise set up karna hai taaki **har size
variant ka apna dimension dikhe** (1 Seater = 38 in, 2 Seater = 58 in, 3 Seater = 78 in).

---

## 1. Pehle wala block fail kyun hua tha

Do alag-alag problems thi — ek code ki, ek data ki.

| # | Problem | Result | Fix |
|---|---------|--------|-----|
| 1 | `{{ variant.metafields.custom.width \| json }}` — metafield ek **object** hai, string nahi. `\| json` uspe lagaya gaya tha. | Embedded JSON corrupt/object-valued banta tha → `JSON.parse` throw → JS silently `return` → **variant change pe kuch update hi nahi hota tha** | Naya `snippets/dews-mf-value.liquid` har metafield ko pehle plain **string** me badalta hai, tab `| json` lagta hai |
| 2 | Variant ids JSON me **bina quotes** ke key bane the (`{4001:"38 in"}`) | Invalid JSON | `variant.id | append: '' | json` → `"4001"` |
| 3 | Metafield definitions **Product** level pe thi, Variant level pe nahi | Har size same value dikhata | Neeche Step 1 dekho + block me **per-size fallback map** add kiya hai |
| 4 | Fallback `change` listener picker ke turant baad `input[name="id"]` padhta tha, jo Dawn **async fetch ke baad** update karta hai | Purani variant ki value lag jaati (race) | Ab sirf Dawn ke post-fetch signals use hote hain |
| 5 | Unavailable combination pe Dawn `variantChange` publish hi nahi karta | Stale dimensions reh jaate | `input[name="id"]` change listener + `is-unavailable` state |
| 6 | `main-product.liquid` line 46: `</script>"` — stray quote | Page pe literal `"` render hota tha | Removed |
| 7 | Nested loop ke baad `forloop.first` pe comma logic depend karta tha | JSON me stray `,` | Explicit counters (`dews_n_row`, `dews_n_v`, `dews_n_k`) |
| 8 | Value me `</script>` ho to script tag toot jaata | Broken page | JSON me `<` `>` `&` ko `\u003c` `\u003e` `\u0026` me escape kiya |

---

## 2. STEP 1 — VARIANT metafield definitions banao (sabse zaroori)

> ⚠️ **Yahi 90% cases me asli wajah hoti hai.** Agar definition **Products** level pe
> hai to ek hi value poori product ki hoti hai — size ke hisaab se badal hi nahi sakti.
> Definition **Variants** level pe honi chahiye.

1. Shopify Admin → **Settings** → **Custom data**
2. **Products** kholo, phir andar **Variants** tab pe jao  ← *Products tab nahi!*
3. **Add definition**
4. Har dimension ke liye ek definition banao:

| Name | Namespace and key | Type |
|------|-------------------|------|
| Width | `custom.width` | Single line text |
| Depth | `custom.depth` | Single line text |
| Height | `custom.height` | Single line text |
| Seat height | `custom.seat_height` | Single line text |
| Weight *(optional)* | `custom.weight` | Single line text |
| Seating capacity *(optional)* | `custom.capacity` | Single line text |

Material & Care block ke liye (agar use karna hai):

| Name | Namespace and key | Type |
|------|-------------------|------|
| Material | `custom.material` | Single line text |
| Finish | `custom.finish` | Single line text |
| Care | `custom.care` | **Multi-line text** (taaki line breaks preserve hon) |

**Type note:** `Single line text` sabse safe hai — value me unit khud likh do
(`38 in` ya `96 cm`). Block `number_integer`, `number_decimal`, `dimension`,
`weight`, `volume`, `list.*`, `boolean` aur `rich_text_field` types ko bhi handle
karta hai, lekin text type me sabse zyada control milta hai.

---

## 3. STEP 2 — har variant ki value bharo

1. **Products** → product kholo
2. **Variants** section tak scroll karo → ek variant pe click karo (e.g. *1 Seater*)
3. Neeche **Metafields** section me values bharo:

```
1 Seater  →  width: 38 in   depth: 34 in   height: 31 in   seat_height: 18 in
2 Seater  →  width: 58 in   depth: 34 in   height: 31 in   seat_height: 18 in
3 Seater  →  width: 78 in   depth: 34 in   height: 31 in   seat_height: 18 in
```

4. **Save**
5. Baaki variants ke liye repeat

### Bulk me karna ho to

> Shopify ke official docs ke mutabik **variant metafields product CSV import/export
> me support nahi hote** — CSV me daaloge to Shopify bina warning ke ignore kar dega.

Isliye bulk ke liye ye options hain:

- **Variant bulk editor** — Admin → Products → products select karo → *Edit products* →
  columns add karo (limited lekin built-in)
- **Matrixify (Excelify)** app — variant metafields CSV se import/export kar sakta hai
- **Metafields Guru** / **BulkFlow** — metafield-specific bulk editors
- **Admin API** — `productVariantUpdate` mutation se scripted bulk update

Chhote catalogue (jaise furniture, jahan 3–6 sizes hote hain) ke liye manual entry
hi sabse fast hai.

---

## 4. STEP 3 — theme editor me verify karo

1. **Online Store → Themes → Customize**
2. Koi product page kholo (template: `product`)
3. Left panel me **Product information** section → **Dimensions** block select karo
4. Sabse neeche **"Show debug table"** ON karo

Ab block ke neeche ek table dikhega — **har variant × har row**, aur har cell me ek
badge batata hai value **kahan se aayi**:

| Badge | Matlab |
|:---:|--------|
| **V** | ✅ Variant metafield — ye chahiye. Size ke saath badlega. |
| **S** | Per-size fallback map (block settings se) — bhi size-specific hai |
| **P** | ⚠️ Product metafield — **har size same dikhega**. Definition Variants tab pe nahi hai. |
| **F** | ⚠️ Static fallback — har size same dikhega |
| **-** | ❌ Kuch nahi mila — row hide ho jaayegi |

**Agar sab badges `P` ya `F` dikh rahe hain → Step 1 galat hua hai, definitions
Product level pe hain.** Debug table sirf theme editor me dikhta hai, storefront pe
kabhi render nahi hota.

Verify karne ke baad debug table OFF kar dena.

---

## 5. Block settings reference

**Dimensions (variant-aware)** block — `Product information` section ke andar:

| Setting | Kaam |
|---------|------|
| Heading | Block ka title (default: *Dimensions*) |
| Tiles per row | 2 / 3 / 4 (default 4; mobile pe hamesha 2) |
| Note under the values | Chhota caption (default: *All dimensions in inches*) |
| **How the values are stored** | `One metafield per row` (recommended) ya `Auto rows from one JSON metafield` |
| Metafield namespace | Default `custom` |
| JSON metafield key | Sirf JSON mode me use hota hai |
| Row 1–6 → Show this row | Row on/off |
| Row 1–6 → Label | Dikhne wala naam (default: Width / Depth / Height / Seat height) |
| Row 1–6 → **Metafield key** | Variant metafield ki key, **namespace ke bina** (e.g. `width`) |
| Row 1–6 → Static fallback value | Jab kuch na mile tab ye dikhega |
| Row 1–6 → **Per-option fallback map** | Neeche section 6 dekho |
| Message for unavailable combinations | Jab koi option combo available na ho |
| Show debug table | Sirf theme editor me |

Icon automatically label/key se choose hota hai — `width`, `depth`, `height`,
`seat`, `weight`, `capacity`, `material`, `finish`, `care`, `warranty` ke liye
alag-alag SVG hai, baaki ke liye generic ruler.

Rows by default: **Width, Depth, Height, Seat height** ON; **Weight, Seating capacity** OFF.

**Material & Care (variant-aware)** block bhi bilkul same settings use karta hai,
bas layout `rows` (label : value list) hai aur default rows Material / Finish / Care hain.

---

## 6. Value resolve hone ka order

Har row, har variant ke liye — **sabse specific pehle**:

```
1. VARIANT metafield      ← custom.width us variant pe
2. Per-option size map    ← block settings se
3. PRODUCT metafield      ← custom.width poori product pe
4. Static fallback value  ← block settings se
(kuch nahi mila → row hide)
```

Size map ko product metafield se **upar** rakha gaya hai jaan-boojh kar — ek
size-specific value hamesha product-wide value se zyada specific hoti hai.

---

## 7. Bina metafields ke kaam chalana ho — per-size map

Agar abhi variant metafields nahi banana chahte, to block settings me
**"Per-option fallback map"** bhar do. Ek line per option value:

```
1 Seater: 38 W x 34 D x 31 H in
2 Seater: 58 W x 34 D x 31 H in
3 Seater: 78 W x 34 D x 31 H in
```

Matching **case-insensitive** hoti hai aur variant ke **kisi bhi option value** se
match karti hai (Size, Colour, Material — jo bhi ho). Agar option value exact na
mile to variant **title** me dhundhta hai (e.g. title `1 Seater / Oak` me `1 Seater` mil jaayega).

Note:
- Format `Option value: value` — pehla `:` separator hai, value me `:` mat daalna
- Ye per-block, per-row hai — har size ke liye alag map dobara likhna padta hai,
  isliye long-term **variant metafields hi better hain**

---

## 8. JSON mode (ek hi metafield me saare dimensions)

Agar tumne ek JSON metafield banaya hai (e.g. `custom.dimensions`) jisme poori
spec sheet hai:

```json
{ "Width": "38 in", "Depth": "34 in", "Height": "31 in", "Seat Height": "18 in" }
```

To block me:
- **How the values are stored** → `Auto rows from one JSON metafield`
- **JSON metafield key** → `dimensions`

Har JSON property apne aap ek row ban jaati hai (JSON ke order me), aur label
property name se aata hai. Variant switch pe poora set badal jaata hai.

---

## 9. Kaise kaam karta hai (technical)

**Server-side** — `snippets/dews-spec-block.liquid`:
- `product.selected_or_first_available_variant` ke liye render karta hai, isliye
  first paint, no-JS visitors aur SEO/crawlers ko hamesha sahi value milti hai
- Saath hi **har variant** ki resolved values ek `<script type="application/json">`
  me embed kar deta hai

**Client-side** — `assets/dews-pdp.js` (`<dews-variant-info>` custom element):

Teen independent triggers, **sab Dawn ke fetch ke BAAD** fire hote hain (isliye koi
race condition nahi):

1. Dawn ka pubsub `variantChange` event — isme freshly rendered section HTML bhi
   aata hai, to Liquid ka apna output hi use hota hai (sabse accurate)
2. Product form ke `input[name="id"]` pe `change` — Dawn ise fetch ke baad set
   karta hai. **Unavailable combination ka signal sirf yahi milta hai**
3. Element dobara connect hona — jab Dawn poora `<product-info>` swap karta hai

Value resolution priority: fresh server HTML → embedded JSON → jo Liquid ne print
kiya wo chhod do.

Extra safety:
- `knowsVariant()` check — agar page pe do `product-info` hon (jaise featured-product
  section) to doosre product ka event ignore hota hai
- `data-section-id` guard
- JSON parse fail ho to `console.warn` + server-rendered value intact rehti hai
- `disconnectedCallback` me unsubscribe (koi memory leak nahi)

**Testing** — `./tools/run-tests.sh` (90 checks, sab pass):
- 56 Liquid render checks — real snippets, fake Shopify data
- 24 JS unit checks — real `assets/dews-pdp.js` in jsdom
- 10 end-to-end checks — Liquid output → jsdom → simulated size click

**Live demo** — `python3 tools/preview/build.py` phir `tools/preview/` ko serve karo.
Char scenarios side-by-side dikhata hai: variant metafields ✅, product-only ⚠️
(purana bug), per-size map ✅, aur kuch metafields missing.

---

## 10. Troubleshooting

| Symptom | Wajah | Fix |
|---------|-------|-----|
| Sab sizes same dimension dikhate hain | Definitions Product level pe hain (debug badge `P`) | Step 1 — **Variants** tab pe definitions banao |
| Block hi nahi dikhta | Koi value resolve nahi hui | Theme editor me block kholo — empty-state placeholder dikhega; keys check karo |
| Storefront pe dikhta hai, editor me nahi | Block `Product information` section me add nahi hai | Customize → product template → *Add block* → **Dimensions (variant-aware)** |
| Values hain lekin switch pe change nahi hota | Browser cache / purana `dews-pdp.js` | Hard refresh; theme re-upload karo; DevTools → Network → `dews-pdp.js` 200 hona chahiye |
| Ek row gayab ho jaati hai | Us variant ke liye wo metafield khaali hai (`null`) | Expected behaviour — row hide hoti hai. Chahiye to fallback/size map bharo |
| `custom` ke alawa namespace use kiya | Bracket lookup | Block me **Metafield namespace** setting update karo |
| Key `size`, `first` ya `last` hai | Ye Liquid filter names se collide karte hain | Snippet me bracket notation already handle karta hai — phir bhi `size` jaisi key se bacho, `dimensions` ya `width` use karo |

---

## 11. Files

**Naye:**
```
snippets/dews-mf-value.liquid      metafield object -> safe plain text
snippets/dews-spec-resolve.liquid  ek row + ek variant ke liye 4-level fallback
snippets/dews-spec-block.liquid    poora block markup + per-variant JSON + debug table
tools/                             test harness (theme me push nahi hota)
```

**Badle:**
```
sections/main-product.liquid       dimensions + material_care blocks & schema; stray quote fix
assets/dews-pdp.js                 <dews-variant-info> custom element (poora rewrite)
assets/component-dews-product.css  .dews-spec styles (tiles + rows + debug + unavailable)
```

**Unchanged (already correct):** `templates/product.json` — `dimensions_dews` aur
`material_care_dews` blocks pehle se `variant_picker` ke turant baad lage hain, aur
block type names same rakhe gaye hain, isliye template ko chhune ki zarurat nahi padi.

> `tools/`, `docs/`, `*.md` aur `*.zip` `.shopifyignore` me hain — `shopify theme push`
> inhe live theme me nahi bhejega.
