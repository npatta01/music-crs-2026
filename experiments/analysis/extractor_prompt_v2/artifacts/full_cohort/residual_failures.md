# v2c × gemma-4-26b residual-failure analysis on full cohort

**Total turns:** 2744    **OK:** 2741    **Errored:** 3 (0.1%)

## A. Tag-recovery distribution
- Turns with ≥1 recovered missed token: **66.2%**
- Mean per-turn recovery rate (of missed tokens): **52.9%**

## C. Era → `release_date` hard_filter conversion
- Turns with an era word in tags: **947**
- ... with the matching `release_date` hard_filter: **616** (65.0%)

Example era-without-filter turns:
- 69498988 t2: era words ['90s'] in tags ['90s', 'New York', 'iconic', 'classic', 'hip-hop']
- 4ec03a54 t6: era words ['modern'] in tags ['deep', 'lyrical', 'modern']
- ac4c8221 t6: era words ['2000s'] in tags ['technical death metal', 'progressive death metal', 'mid-2000s']
- 5080d5a0 t5: era words ['modern'] in tags ['bop', 'classic funk', 'funk', 'R&B', 'classic R&B', 'modern']
- d265b5a9 t4: era words ['2010s'] in tags ['electronic', '2010s', 'striking', 'abstract', 'creative', 'cover art', 'strong visual identity']
- d5bfd0f3 t8: era words ['modern'] in tags ['modern', 'Christmas', 'popular', 'holiday']
- de0cfc6d t8: era words ['contemporary'] in tags ['electronic', 'chill', 'ambient', 'contemporary']
- a9b423bf t3: era words ['90s'] in tags ['dope', 'classic', '90s', 'underground', 'sound', 'production', 'fire', 'deep cuts', 'era', 'jazzy', 'soulful', 'vibe']

## D. Reaction-word leakage (tags like 'awesome', 'great', 'love', etc.)
- Turns with at least one reaction word as a positive tag: **57** (2.1%)

Top leaked tokens:
- 22× `cool`
- 6× `love`
- 5× `great`
- 5× `fantastic`
- 5× `awesome`
- 4× `amazing`
- 3× `brilliant`
- 2× `good`
- 2× `incredible`
- 2× `wonderful`
- 1× `perfect`

Example reaction-leak turns:
- b3d673d4 t7: leaked=['good'] all_tags=['good', 'heroic journey feel', 'strong orchestra', 'brass', 'powerful', 'orchestral', 'exploring', 'mysterious', 'ancient ruin']
- 12a2dcc1 t4: leaked=['cool'] all_tags=['striking', 'trippy', 'cool', 'raw', 'psychedelic rock', 'psychedelic', 'rock', 'abstract', 'surreal', 'indie rock', 'indie', 'folk-rock', 'folk']
- 451e7e67 t6: leaked=['brilliant'] all_tags=['brilliant', 'chill', 'intricate', 'electronic', 'deep', 'atmospheric', 'downtempo', 'beats']
- a2a714a4 t7: leaked=['amazing'] all_tags=['amazing', 'moving', 'legendary', 'Celtic', 'traditional', 'Irish landscape']
- 98efe728 t3: leaked=['love'] all_tags=['intimate', 'deeper', 'complex', 'introspective', 'love', 'connection', 'emotional story']
- f5eafdb9 t6: leaked=['great'] all_tags=['great', 'groovy', 'bassline', '2010s', 'upbeat', 'alternative rock', 'strong vocals', 'good bassline']
- 4bed64e6 t5: leaked=['cool'] all_tags=['cool', 'memorable', 'guitar riff', 'catchy']
- 94f1f3c9 t7: leaked=['fantastic'] all_tags=['fantastic', 'driving riff', 'raw energy', 'extremely famous', 'instantly identifiable', 'quintessential', 'no-frills', 'loud rock anthem', 'male vocals', 'distinct', 'powerful']

## E. Hallucination
- Total hallucinated tag instances (not in conv text): **42**
- Share of all emitted tags that are hallucinations: **0.26%**

Top hallucinated tokens:
- 3× `hip hop`
- 1× `[track] jingle bell rock - daryl's version`
- 1× `dramatic vocals`
- 1× `[artist] wino`
- 1× `[track] little fluffy clouds - dance mix 2`
- 1× `[artist] daphni`
- 1× `new perspective`
- 1× `extremely famous`
- 1× `[track] a taste of honey - live`
- 1× `1996`
- 1× `lyrical`
- 1× `[artist] howard shore`
- 1× `lyric:here comes the sun, little darlin'`
- 1× `lyric:imagine all the people living life in peace`
- 1× `[track] word salad (98 reissue)`
- 1× `lyric:yesterday all my troubles seemed so far away`
- 1× `atmospheric electronic`
- 1× `indie pop vibe`
- 1× `female band`
- 1× `lyric:i just wanna take you on a ride with me, see the world with me`

## F. Top still-missed tokens (classifier reports missed; gemma-4 didn't emit)
- 186× `love`
- 120× `good`
- 118× `classic`
- 113× `great`
- 77× `awesome`
- 63× `one`
- 60× `cool`
- 50× `can`
- 48× `sound`
- 44× `what`
- 40× `have`
- 31× `perfect`
- 31× `yes`
- 30× `lyrics`
- 30× `new`
- 30× `feel`
- 28× `beautiful`
- 28× `rock`
- 28× `artists`
- 25× `all`
- 24× `really`
- 23× `time`
- 23× `bands`
- 22× `was`
- 18× `are`
- 16× `something`
- 15× `out`
- 14× `beatles`
- 14× `play`
- 14× `amazing`

## G. Empty-output turns (zero tags AND zero named entities)
- **1** turns (0.0%)