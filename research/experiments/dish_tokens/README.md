# Token cost of the naive dish-selection call

Question: how cheaply can the naive selection call (dish names + owned ingredients in, dishes with have/missing out) run without losing answer quality? Variants, the quality baseline and the decision rule are fixed in `criteria.json`, committed before any call of this study (together with `../dish_pipeline/criteria.json`). Same 12 inputs as the pipeline study (seeded sample of the frozen naive inputs).

Image resolution was reduced earlier for recognition; here the corresponding levers are the output budget, the answer schema, the prompt layout, the reasoning setting and prefix caching.

Results are added below after the runs.
