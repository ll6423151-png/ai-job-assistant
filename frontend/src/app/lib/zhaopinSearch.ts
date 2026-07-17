type CandidateVisibility = {
  eligible: boolean;
  job_id: number | null;
  auto_blacklisted: boolean;
  import_action?: "created" | "updated" | null;
};

function visibilityPriority(candidate: CandidateVisibility) {
  if (candidate.import_action === "created") return 5;
  if (candidate.import_action === "updated") return 4;
  if (candidate.job_id !== null) return 3;
  if (candidate.eligible) return 2;
  if (candidate.auto_blacklisted) return 1;
  return 0;
}

export function prioritizeZhaopinCandidates<T extends CandidateVisibility>(
  candidates: T[],
  limit = 10,
): T[] {
  return candidates
    .map((candidate, index) => ({ candidate, index }))
    .sort((left, right) => (
      visibilityPriority(right.candidate) - visibilityPriority(left.candidate)
      || left.index - right.index
    ))
    .slice(0, limit)
    .map(({ candidate }) => candidate);
}

export function countNewJobIds(
  previousIds: Iterable<number>,
  currentIds: Iterable<number>,
) {
  const previous = new Set(previousIds);
  return [...currentIds].filter((id) => !previous.has(id)).length;
}
