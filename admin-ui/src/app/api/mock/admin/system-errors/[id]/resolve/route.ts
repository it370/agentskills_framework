// Mock API route for resolving errors
// Remove this file when using real backend

import { NextResponse } from 'next/server';

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return NextResponse.json({
    status: "success",
    message: `Error ${id} marked as resolved (mock)`,
    error_id: parseInt(id),
    resolved_by: "mock_admin@example.com"
  });
}
