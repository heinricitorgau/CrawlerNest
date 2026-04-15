"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

export default function UniversityPreviewPage() {
  const searchParams = useSearchParams();
  const canonicalUniversityId = searchParams.get("canonicalUniversityId");
  const universityName = searchParams.get("universityName");

  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!canonicalUniversityId && !universityName) {
      setError("Invalid query");
      setLoading(false);
      return;
    }

    let url = "/api/university-preview?";

    if (canonicalUniversityId) {
      url += `canonicalUniversityId=${canonicalUniversityId}`;
    } else {
      url += `universityName=${encodeURIComponent(universityName!)}`;
    }

    fetch(url)
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error("University not found");
          if (res.status === 400) throw new Error("Invalid query");
          throw new Error("Failed to fetch");
        }
        return res.json();
      })
      .then((json) => {
        setData(json.data);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [canonicalUniversityId, universityName]);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div style={{ padding: "20px" }}>
      <h1>University Preview</h1>

      <div>
        Query:
        {canonicalUniversityId
          ? ` canonicalUniversityId=${canonicalUniversityId}`
          : ` universityName=${universityName}`}
      </div>

      <pre style={{ marginTop: "20px" }}>
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
