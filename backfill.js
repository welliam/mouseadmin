const reviews = [
  "https://dumbiee.neocities.org/reviews/ai-the-somnium-files.html",
  "https://dumbiee.neocities.org/reviews/alone-in-the-dark.html",
  "https://dumbiee.neocities.org/reviews/alone-in-the-dark-the-new-nightmare.html",
  "https://dumbiee.neocities.org/reviews/american-arcadia.html",
  "https://dumbiee.neocities.org/reviews/atelier-rorona-the-alchemist-of-arland-dx.html",
  "https://dumbiee.neocities.org/reviews/corn-kidz-64.html",
  "https://dumbiee.neocities.org/reviews/cult-of-the-lamb.html",
  "https://dumbiee.neocities.org/reviews/detroit-become-human.html",
  "https://dumbiee.neocities.org/reviews/dragon-s-crown-pro.html",
  "https://dumbiee.neocities.org/reviews/fire-rock.html",
  "https://dumbiee.neocities.org/reviews/germs-nerawareta-machi.html",
  "https://dumbiee.neocities.org/reviews/granblue-fantasy-relink.html",
  "https://dumbiee.neocities.org/reviews/heavy-rain.html",
  "https://dumbiee.neocities.org/reviews/i-m-on-observation-duty.html",
  "https://dumbiee.neocities.org/reviews/iblard-laputa-no-kaeru-machi.html",
  "https://dumbiee.neocities.org/reviews/indigo-prophecy.html",
  "https://dumbiee.neocities.org/reviews/lies-of-p.html",
  "https://dumbiee.neocities.org/reviews/lunacid.html",
  "https://dumbiee.neocities.org/reviews/lunistice.html",
  "https://dumbiee.neocities.org/reviews/outer-wilds.html",
  "https://dumbiee.neocities.org/reviews/pentiment.html",
  "https://dumbiee.neocities.org/reviews/rayman.html",
  "https://dumbiee.neocities.org/reviews/return-to-atlantis.html",
  "https://dumbiee.neocities.org/reviews/shenmue.html",
  "https://dumbiee.neocities.org/reviews/smash-tennis.html",
  "https://dumbiee.neocities.org/reviews/subnautica.html",
  "https://dumbiee.neocities.org/reviews/the-outer-worlds.html",
  "https://dumbiee.neocities.org/reviews/zelda-the-ultimate-trial.html"
];

async function parseReviews(reviews) {
    const results = []

    const domParser = new DOMParser();
    for (const reviewUrl of reviews) {
        const result = await fetch(reviewUrl).then(x => x.text());
        const reviewHtml = document.createElement('div')
        reviewHtml.innerHTML = result;
        const gameData = reviewHtml.querySelector('#game-house').dataset;

        results.push({
            title: gameData.title,
            art_url: gameData.artUrl,
            developer: gameData.developer,
            rating: gameData.rating,
            platform: gameData.platform,
            completion: gameData.completion,
            method: gameData.method,
            date: gameData.date,
            emulated: gameData.emulated,
            review: reviewHtml.querySelector('#game-review-content').innerHTML,
            recommendation: reviewHtml.querySelector('#game-rec-answer').innerHTML,
            extras: reviewHtml.querySelector('#extras')?.innerHTML,
        });

        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    console.log(results);
}

parseReviews(reviews);
