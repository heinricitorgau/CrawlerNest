import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const canonicalUniversityId = searchParams.get("canonicalUniversityId");
  const universityName = searchParams.get("universityName");

  if (!canonicalUniversityId && !universityName) {
    return NextResponse.json(
      { success: false, error: "Invalid query" },
      { status: 400 }
    );
  }

  let backendUrl = "http://localhost:8080/api/v1/preview/universities?";

  if (canonicalUniversityId) {
    backendUrl += `canonicalUniversityId=${canonicalUniversityId}`;
  } else {
    backendUrl += `universityName=${encodeURIComponent(universityName!)}`;
  }

  try {
    const response = await fetch(backendUrl, {
      cache: "no-store",
    });

    if (!response.ok) {
      // Return the backend's status and body
      const body = await response.text();
      return new NextResponse(body, {
        status: response.status,
        headers: { "Content-Type": "application/json" },
      });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to reach backend:", error);
    return NextResponse.json(
      { success: false, error: "Failed to reach backend preview API" },
      { status: 502 }
    );
  }
}