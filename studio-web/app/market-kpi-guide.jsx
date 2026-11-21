import { Table, dateLabel, label, number, percent } from "./market-shared";

const monthLabel = (month) =>
  dateLabel(month + "-01", { month: "short", year: "numeric" });

function Guide({ context, reading, children, breakdown, headers, rows }) {
  return (
    <div className="mk-kpi-guide">
      <div className="mk-kpi-reading">
        <small>{context}</small>
        <p>{reading}</p>
      </div>
      {children}
      {rows.length > 0 && (
        <details>
          <summary>{breakdown}</summary>
          <Table headers={headers} rows={rows} />
        </details>
      )}
    </div>
  );
}

function Explanation({ title, children }) {
  return (
    <section>
      <h3>{title}</h3>
      <p>{children}</p>
    </section>
  );
}

export function OpportunityGuide({
  context,
  chosen,
  rank,
  rankedCount,
  gapCount,
  rows,
}) {
  const score = chosen?.opportunity_score;
  const peerShare = chosen?.dk_share == null ? null : 1 - chosen.dk_share;
  return (
    <Guide
      context={context}
      reading={
        score == null ? (
          <>
            This category is <strong>unranked</strong>.{" "}
            {chosen?.forecast_growth == null
              ? "There is too little review history to estimate growth."
              : "The review sample needs coverage of all six brands to estimate Dot & Key’s share."}
          </>
        ) : (
          <>
            A score of <strong>{number(score, 3)}</strong> puts this category at{" "}
            <strong>
              rank {rank} of {rankedCount}
            </strong>{" "}
            in this comparison.
          </>
        )
      }
      breakdown="Compare scores across categories"
      headers={["Category", "Score", "Forecast growth", "D&K review share"]}
      rows={rows}
    >
      <Explanation title="What earns a higher rank?">
        The chart ranks categories from the highest score (rank 1) to the
        lowest. In a growing category, more reviews going to other brands and
        more gaps both raise its score. A gap can be a recurring complaint, an
        unmet need or a product option missing from the tracked range.
      </Explanation>
      <section>
        <h3>How this score is calculated</h3>
        <p>Multiply these three figures to get the score.</p>
        <dl className="mk-kpi-factors">
          <div>
            <dt>
              Expected growth in review activity over the next three months
            </dt>
            <dd>{percent(chosen?.forecast_growth, true)}</dd>
          </div>
          <div>
            <dt>Share of reviews going to other brands</dt>
            <dd>{percent(peerShare)}</dd>
          </div>
          <div>
            <dt>Number of distinct gaps</dt>
            <dd>{number(gapCount)}</dd>
          </div>
        </dl>
        {score != null && gapCount != null && (
          <p className="mk-kpi-math">
            {percent(chosen.forecast_growth)} × {percent(peerShare)} ×{" "}
            {number(gapCount)} ≈ {number(score, 3)}
          </p>
        )}
        {score === 0 && gapCount === 0 && (
          <p>
            With zero gaps, the score is zero even when activity is growing.
          </p>
        )}
        {score < 0 && (
          <p>A negative score reflects a projected decline in activity.</p>
        )}
        {score == null && (
          <p>
            A dash marks an unavailable figure. The category gets a rank once
            all three figures are available.
          </p>
        )}
      </section>
    </Guide>
  );
}

function shareBasis(data) {
  const markets = (data.marketplaces || []).map(label).join(", ");
  switch (data.source) {
    case "listing_review_counts":
      return `The counts come from the review totals shown on tracked ${markets} product listings.`;
    case "dated_review_sample":
      return `The counts use dated review texts collected from ${markets} over the previous 12 complete months.`;
    case "full_review_sample":
      return `The counts use review texts collected from ${markets} through the reporting date.`;
    case "one_marketplace_per_product_sample":
      return "Each product contributes collected reviews from one marketplace that carries both Dot & Key and competitors.";
    default:
      return "The comparison uses reviews for Dot & Key and five tracked competitors.";
  }
}

export function ReviewShareGuide({ context, data, compare }) {
  const hasCounts =
    data.value != null &&
    data.dk_review_volume != null &&
    data.top_six_review_volume > 0;
  return (
    <Guide
      context={context}
      reading={
        data.value == null ? (
          <>
            The sample needs reviews covering all six brands before it can show
            Dot &amp; Key’s share.
          </>
        ) : (
          <>
            <strong>{percent(data.value)}</strong> of the reviews counted across
            six brands were for Dot &amp; Key.
            {hasCounts && (
              <>
                {" "}
                That’s{" "}
                <strong>
                  {number(data.dk_review_volume)} out of{" "}
                  {number(data.top_six_review_volume)}
                </strong>{" "}
                reviews.
              </>
            )}
          </>
        )
      }
      breakdown="See counts and ratings by marketplace"
      headers={[
        "Marketplace",
        "D&K review texts",
        "Ratings counted",
        "Average stars out of 5",
      ]}
      rows={(data.markets || []).map((r) => [
        label(r.market),
        number(r.review_volume),
        number(r.rating_count),
        number(r.rating, 2),
      ])}
    >
      <Explanation title="Which reviews count?">
        {shareBasis(data)} Divide Dot &amp; Key’s count by the total for all six
        brands and multiply by 100.
      </Explanation>
      <Explanation title="Change since the comparison date">
        {data.delta == null ? (
          data.value != null ? (
            `There is no comparable share for ${dateLabel(compare)}, so the card has no change figure for this period.`
          ) : (
            `A change needs a share for both this report and the comparison on ${dateLabel(compare)}.`
          )
        ) : (
          <>
            Share was <strong>{percent(data.previous)}</strong> on{" "}
            {dateLabel(compare)} and is <strong>{percent(data.value)}</strong>{" "}
            on the reporting date.{" "}
            {data.delta === 0
              ? "The share stayed the same."
              : `That’s ${data.delta > 0 ? "up" : "down"} ${Math.abs(data.delta) < 0.0005 ? "less than 0.1" : number(Math.abs(data.delta) * 100, 1)} percentage points.`}{" "}
            “pp” means percentage points, the difference between two
            percentages.
          </>
        )}
      </Explanation>
      <Explanation title="How to read the marketplace bars">
        Each bar counts written Dot &amp; Key reviews collected on that
        marketplace. The longest bar has the most texts. The star value is the
        average product rating out of 5, giving more weight to listings with
        more ratings. A dash means a rating is unavailable.
      </Explanation>
    </Guide>
  );
}

export function DemandGuide({ context, data, observed }) {
  const series = data.series || [];
  const projection = data.projection || [];
  const ratings =
    data.activity_unit === "ratings" ||
    data.source === "stable same-listing rating-count increments";
  const unit = ratings ? "new ratings" : "dated reviews";
  const difference = observed ? observed.index - 100 : 0;
  const hasCounts = series.some((r) => r.activity !== undefined);
  const rows = [
    ...series.map((r) => [
      monthLabel(r.month),
      "History",
      ...(hasCounts ? [number(r.activity, 1)] : []),
      number(r.index, 2),
    ]),
    ...projection.map((r) => [
      monthLabel(r.month),
      "Forecast",
      ...(hasCounts ? ["—"] : []),
      number(r.index, 2),
    ]),
  ];
  return (
    <Guide
      context={context}
      reading={
        observed ? (
          <>
            An index of <strong>{number(observed.index, 1)}</strong> means
            activity in {monthLabel(observed.month)} was{" "}
            <strong>
              {Math.abs(difference) < 0.05
                ? "at the recent average"
                : `${number(Math.abs(difference), 1)}% ${difference > 0 ? "above" : "below"} the recent average`}
            </strong>
            .
          </>
        ) : (
          <>
            This category is <strong>awaiting data</strong>. The available
            activity is too limited to calculate an index or forecast.
          </>
        )
      }
      breakdown="See monthly activity and index values"
      headers={[
        "Month",
        "Period",
        ...(hasCounts ? [label(unit)] : []),
        "Index",
      ]}
      rows={rows}
    >
      <Explanation title="Why 100 is the reference point">
        An index of 100 is the average monthly activity over the last three
        complete months.
        {data.baseline != null && observed?.activity != null ? (
          <>
            {" "}
            Here that average is{" "}
            <strong>
              {number(data.baseline, 1)} {unit}
            </strong>{" "}
            per month. {monthLabel(observed.month)} had{" "}
            <strong>{number(observed.activity, 1)}</strong>.
          </>
        ) : (
          " For example, 120 means 20% more activity than that average."
        )}{" "}
        {ratings
          ? "We estimate new star ratings from changes in the totals on the same product listings over time."
          : "Activity counts dated reviews from marketplaces where both Dot & Key and competitors have reviews."}
      </Explanation>
      {observed ? (
        <Explanation title="How to read the forecast">
          The solid line shows observed activity. The dashed line extends the
          monthly trend to estimate the next three months.
          {data.forecast_growth != null && (
            <>
              {" "}
              The forecast badge shows{" "}
              <strong>{percent(data.forecast_growth, true)}</strong>. Over those
              three months, average activity is expected to be{" "}
              {data.forecast_growth === 0
                ? "level with"
                : `${percent(Math.abs(data.forecast_growth))} ${data.forecast_growth > 0 ? "above" : "below"}`}{" "}
              the recent average.
            </>
          )}
        </Explanation>
      ) : (
        <Explanation title="What the forecast needs">
          The past year must include at least six months with data and at least
          30 observations. Each of the last three complete months needs data,
          with an average above zero.
          {data.observations != null && (
            <>
              {" "}
              This sample contains{" "}
              <strong>
                {number(data.observations, 1)} {unit}
              </strong>
              .
            </>
          )}{" "}
          A dash in the table means a value is unavailable.
        </Explanation>
      )}
    </Guide>
  );
}

export function ActivityGuide({ context, rows, total, peak, launch }) {
  const unit = launch ? "launch candidate" : "review";
  return (
    <Guide
      context={context}
      reading={
        launch ? (
          <>
            The tracked competitor catalogs show{" "}
            <strong>
              {number(total)} possible product{" "}
              {total === 1 ? "launch" : "launches"}
            </strong>{" "}
            in the 90 days ending on the reporting date.
          </>
        ) : (
          <>
            The sample includes{" "}
            <strong>
              {number(total)} dated {total === 1 ? "review" : "reviews"}
            </strong>{" "}
            for Dot &amp; Key and tracked competitors in the 90 days ending on
            the reporting date.
          </>
        )
      }
      breakdown={
        launch
          ? "See launch candidates by week"
          : "See weekly counts by star rating"
      }
      headers={
        launch
          ? ["Week starting", "Launch candidates"]
          : [
              "Week starting",
              "Reviews",
              "Positive",
              "Neutral",
              "Negative",
              "Unrated",
            ]
      }
      rows={rows.map((r) => [
        dateLabel(r.week),
        number(r.total),
        ...(launch
          ? []
          : [
              number(r.positive),
              number(r.neutral),
              number(r.negative),
              number(r.unrated),
            ]),
      ])}
    >
      <Explanation title="How to read the weeks">
        Each group of dots is a week starting on Monday. Taller groups mean more{" "}
        {unit}s that week. The headline adds up all weeks, including any partial
        weeks at the edges.
        {peak && (
          <>
            {" "}
            The week starting <strong>{dateLabel(peak.week)}</strong> had the
            highest count,{" "}
            <strong>
              {number(peak.total)} {unit}
              {peak.total === 1 ? "" : "s"}
            </strong>
            .
          </>
        )}
      </Explanation>
      {launch ? (
        <Explanation title="What counts as a possible launch?">
          A product newly seen in a competitor’s catalog counts in the week we
          first saw it. For the first catalog we saved, we use the product’s
          listing creation date. These dates tell us when a listing appeared.
          The product may have gone on sale at a different time.
        </Explanation>
      ) : (
        <Explanation title="What the colours mean">
          The colours come from the reviewer’s star rating. Positive means 4 or
          5 stars, neutral means 3, and negative means 1 or 2. Reviews without a
          star rating count towards the total as unrated.
        </Explanation>
      )}
    </Guide>
  );
}
