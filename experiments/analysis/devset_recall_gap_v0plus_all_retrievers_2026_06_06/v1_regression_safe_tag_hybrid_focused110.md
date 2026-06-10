# V1 Regression Safe-Tag Hybrid Focused-110 Probe

Native LanceDB hybrid branch diagnostic: Qwen8 attributes vector query + FTS over catalog-safe V1 attribute tags only.

## Summary

- n: 110
- fired: 81
- errors: 0
- hit@20: 0.00909090909090909
- hit@50: 0.00909090909090909
- hit@100: 0.02727272727272727
- hit@1000: 0.2636363636363636
- safe_tag_turns: 81
- query_turns: 93

## Top Hits

| sample_id | class | gt | rank | safe_tags |
|---|---|---|---:|---|
| `ba3da7b0-1e81-4d2a-90fa-65ee1f4d7348::t1` | positive_control | Heart-Shaped Box / Nirvana | 19 | grunge, 1990s |
| `3676005d-5b7c-4c48-9b73-3e10dd509c07::t1` | failure | Breath and Life / Audiomachine | 53 | early 2000s |
| `1e14a07f-7369-4d24-9285-9343b6b18353::t8` | failure | Nordlys / Myrkur | 56 | dark folk, gothic folk, atmospheric, haunting, ethereal vocals |
| `028027d3-ad67-4cfb-baca-516772ae7399::t1` | positive_control | Toxic / Britney Spears | 103 | iconic |
| `8071d14d-7e0f-4f72-90a6-0941db80a371::t5` | failure | Stay Down / Brent Faiyaz | 125 | chill, R&B, groove |
| `d5fcb591-3744-4ebb-9d1a-5c57c314b7d0::t5` | failure | Love Train / The O'Jays | 131 | R&B/Soul, funky, soulful, late 1970s, golden era |
| `f2d85aa5-2086-4b1e-9974-d188c43621db::t8` | failure | Leraine / Kettel | 131 | ambient electronic, late 2000s, instrumental |
| `55388720-92b7-4972-9bb2-beb37c33c86b::t1` | positive_control | Ivy / Frank Ocean | 161 | 2016 |
| `0b9d547f-e748-464a-90e2-2199149f915c::t6` | failure | Give It To Me Baby / Rick James | 171 | high-energy, classic disco, funk |
| `5861afef-85c0-4163-b8b9-5a11e308f352::t4` | failure | Carmesí / Vicente Garcia | 194 | danceable, Latin |
| `cdd374ea-1ad9-4440-8c2d-4c76c5fb3f78::t3` | failure | Gib ihn einfach (Dies das 2) / Ghanaian Stallion | 196 | old-school hip-hop |
| `2bbc0a7e-3ab0-4376-8135-182cd4ae075f::t1` | failure | Las Almas Del Silencio / Ricky Martin | 236 | Latin Pop, early 2000s |
| `4e2482dc-a76c-4f4b-9d3f-7becec2f8a3a::t4` | failure | Goodbye Pork Pie Hat / Charles Mingus | 242 | classic jazz, bluesy, soulful |
| `a61b366c-8cf5-48ad-a13f-181c033b9d89::t2` | positive_control | Pumped Up Kicks / Foster The People | 249 | indie rock, energetic |
| `9b9b7c6b-b376-4d6b-8716-aa7cf0127322::t4` | failure | The Carbon Stampede / Cattle Decapitation | 273 | recent, technical death metal, progressive death metal |
| `b2582e52-6d13-40b4-8552-2d8b63fa6c75::t8` | failure | Soil / System Of A Down | 310 | alternative metal, heavy, new bands |
| `a8df96e2-c196-462c-9484-72aa093aedf4::t1` | failure | Do Everything / Steven Curtis Chapman | 341 | Christian, male artist |
| `1b406c88-9dfd-42cd-a1f5-9683f35f849b::t1` | failure | 93 'Til Infinity / Souls Of Mischief | 467 | underground hip-hop, 1990s, classic |
| `be88097f-b6b0-4fb4-bed9-857a92a733c0::t3` | failure | Dreams - 2004 Remaster / Fleetwood Mac | 497 | 1970s |
| `54cda581-3b2e-4245-a479-1a27589760d2::t3` | failure | Deliberation - Studio / Katatonia | 522 | heavy metal, dark, abstract, bleak |
