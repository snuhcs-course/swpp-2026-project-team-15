# Model-call pipeline for dishes and YouTube links

Structure (fixed by the product decision): the phone sends its ingredients; the server gives the model the ingredient list and the dish-name list and gets dishes plus YouTube video-id candidates per dish; the server only checks with one batched `videos.list` call that each id exists and is embeddable; the phone shows cards. No title filter, no view sorting, no fixed card or link count.

Question: which arrangement of the model calls is cheapest while the cards appear fast and most dishes keep an embeddable video? Variants P1–P4, metrics, the judge and the decision rule are in `criteria.json`, committed before any call. The selection call uses the winner of `../dish_tokens/`.

Results are added below after the runs.
