type RankingItem = {
  canonicalUniversityId: number;
  universityName: string;
  country: string;
  aggregatedRank: number;
  compositeScore: number;
  rankingYear: number;
  primarySource: string;
  sourceCount: number;
  slug: string;
};

type RankingsResponse = {
  success: boolean;
  data: {
    items: RankingItem[];
  };
  metadata: {
    timestamp: string;
  };
};

async function fetchRankings(): Promise<RankingsResponse> {
  const res = await fetch(
    "http://localhost:8080/api/v1/rankings?page=1&pageSize=20&source=AGGREGATED&year=2026",
    { cache: "no-store" }
  );

  if (!res.ok) {
    throw new Error("Failed to fetch rankings");
  }

  return res.json();
}

export default async function HomePage() {
  let items: RankingItem[] = [];
  let error: string | null = null;
  let timestamp: string | null = null;

  try {
    const result = await fetchRankings();
    items = result.data.items;
    timestamp = result.metadata.timestamp;
  } catch {
    error = "無法載入 rankings 資料，請確認 Spring Boot API 是否正在 localhost:8080 執行。";
  }

  return (
    <main className="min-h-screen bg-white text-gray-900">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-8">
          <h1 className="text-3xl font-bold tracking-tight">
            Global University Rankings
          </h1>
          <p className="mt-2 text-gray-600">
            Structured university ranking data powered by CrawlerNest
          </p>
          {timestamp && (
            <p className="mt-2 text-sm text-gray-400">
              Updated: {new Date(timestamp).toLocaleString()}
            </p>
          )}
        </header>

        {error ? (
          <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700">
            {error}
          </div>
        ) : items.length === 0 ? (
          <div className="rounded-xl border border-gray-200 bg-gray-50 p-6 text-gray-600">
            No ranking data available.
          </div>
        ) : (
          <div className="overflow-hidden rounded-2xl border border-gray-200 shadow-sm">
            <table className="w-full border-collapse">
              <thead className="bg-gray-50 text-sm text-gray-600">
                <tr>
                  <th className="px-4 py-3 text-left">Rank</th>
                  <th className="px-4 py-3 text-left">University</th>
                  <th className="px-4 py-3 text-left">Country</th>
                  <th className="px-4 py-3 text-left">Score</th>
                  <th className="px-4 py-3 text-left">Sources</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.canonicalUniversityId}
                    className="border-t border-gray-100 hover:bg-gray-50"
                  >
                    <td className="px-4 py-4 font-semibold">
                      #{item.aggregatedRank}
                    </td>
                    <td className="px-4 py-4">
                      <div className="font-medium text-gray-900">
                        {item.universityName}
                      </div>
                      <div className="text-sm text-gray-400">
                        /universities/{item.slug}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-700">{item.country}</td>
                    <td className="px-4 py-4 text-gray-700">
                      {item.compositeScore}
                    </td>
                    <td className="px-4 py-4 text-gray-500">
                      {item.sourceCount}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}