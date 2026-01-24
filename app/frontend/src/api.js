// Use relative path - Vite proxy handles routing to backend
const API_BASE = ''

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/api/stats`)
  if (!res.ok) throw new Error('Failed to fetch stats')
  return res.json()
}

export async function fetchItems() {
  const res = await fetch(`${API_BASE}/api/items`)
  if (!res.ok) throw new Error('Failed to fetch items')
  return res.json()
}

export async function fetchPriorityUnits() {
  const res = await fetch(`${API_BASE}/api/priority-units`)
  if (!res.ok) throw new Error('Failed to fetch priority units')
  return res.json()
}

export async function fetchComps(stage) {
  const res = await fetch(`${API_BASE}/api/comps/${stage}`)
  if (!res.ok) throw new Error('Failed to fetch comps')
  return res.json()
}

export async function fetchAugments(tier, rarity) {
  const params = new URLSearchParams()
  if (tier) params.append('tier', tier)
  if (rarity) params.append('rarity', rarity)
  const res = await fetch(`${API_BASE}/api/augments?${params}`)
  if (!res.ok) throw new Error('Failed to fetch augments')
  return res.json()
}

export async function postRecommend(boardState) {
  const res = await fetch(`${API_BASE}/api/recommend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(boardState)
  })
  if (!res.ok) throw new Error('Failed to get recommendations')
  return res.json()
}

export async function postAnalyze(boardState) {
  const res = await fetch(`${API_BASE}/api/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(boardState)
  })
  if (!res.ok) throw new Error('Failed to analyze board')
  return res.json()
}

export async function postLobbyUpdate(compCounts) {
  const res = await fetch(`${API_BASE}/api/lobby`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(
      Object.entries(compCounts).map(([name, count]) => ({ name, count }))
    )
  })
  if (!res.ok) throw new Error('Failed to update lobby')
  return res.json()
}
