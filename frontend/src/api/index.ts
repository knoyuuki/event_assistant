import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// ─── Types ──────────────────────────────────────────────────

export interface Person {
  id: number
  name: string
  department: string
  position: string
  filename: string
  person_type?: string | null
  sort_order?: number | null
  position_title?: string | null
  position_level?: number | null
  managed_departments?: string | null
  managed_businesses?: string | null
  notes?: string | null
  phone?: string | null
  email?: string | null
  created_at?: string | null
}

export interface PersonForm {
  name: string
  department: string
  position: string
  filename: string
  person_type?: string | null
  sort_order?: number | null
  position_title?: string | null
  position_level?: number | null
  managed_departments?: string | null
  managed_businesses?: string | null
  notes?: string | null
  phone?: string | null
  email?: string | null
}

export interface DeptCategory {
  id: number
  name: string
  sort_order: number
  created_at?: string | null
}

export interface DeptCategoryForm {
  name: string
  sort_order?: number | null
}

export interface Department {
  id: number
  name: string
  category_id?: number | null
  sort_order: number
  description?: string | null
  created_at?: string | null
}

export interface DepartmentForm {
  name: string
  category_id?: number | null
  sort_order?: number
  description?: string | null
}

export interface DepartmentTreeNode {
  id: number | null
  name: string
  sort_order: number
  created_at?: string | null
  departments: Department[]
}

export interface ReorderItem {
  id: number
  sort_order: number
}

export interface AnswerItem {
  id: number
  name: string
}

export interface CheckResult {
  total: number
  correct: number
  score: number
  details: Array<{
    id: number
    correct_name: string
    user_answer: string
    is_correct: boolean
  }>
}

export interface PositionLevelMap {
  mapping: Record<string, number>
  aliases: Record<string, string>
  default_level: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

// ─── Person API ─────────────────────────────────────────────

export function fetchPersons(params?: {
  department?: string
  person_type?: string
  position_level?: number
  search?: string
  page?: number
  page_size?: number
}) {
  return api.get<PaginatedResponse<Person>>('/persons', { params })
}

export function fetchPersonsSequential(department?: string) {
  return api.get<Person[]>('/persons/sequential', { params: { department } })
}

export function fetchPersonsRandom(department?: string) {
  return api.get<Person[]>('/persons/random', { params: { department } })
}

export function fetchPerson(id: number) {
  return api.get<Person>(`/persons/${id}`)
}

export function createPerson(data: PersonForm) {
  return api.post<Person>('/persons', data)
}

export function updatePerson(id: number, data: Partial<PersonForm>) {
  return api.put<Person>(`/persons/${id}`, data)
}

export function deletePerson(id: number) {
  return api.delete(`/persons/${id}`)
}

export function reorderPersons(items: ReorderItem[]) {
  return api.put('/persons/reorder', items)
}

// ─── Person Types API ────────────────────────────────────────

export function fetchPersonTypes() {
  return api.get<{ types: string[] }>('/person-types')
}

// ─── Department Category API ────────────────────────────────

export function fetchDeptCategories() {
  return api.get<DeptCategory[]>('/dept-categories')
}

export function createDeptCategory(data: DeptCategoryForm) {
  return api.post<DeptCategory>('/dept-categories', data)
}

export function updateDeptCategory(id: number, data: Partial<DeptCategoryForm>) {
  return api.put<DeptCategory>(`/dept-categories/${id}`, data)
}

export function deleteDeptCategory(id: number) {
  return api.delete(`/dept-categories/${id}`)
}

export function reorderDeptCategories(items: ReorderItem[]) {
  return api.put('/dept-categories/reorder', items)
}

// ─── Department API ─────────────────────────────────────────

export function fetchDepartments() {
  return api.get<Department[]>('/departments')
}

export function fetchDepartmentsTree() {
  return api.get<DepartmentTreeNode[]>('/departments', { params: { tree: true } })
}

export function fetchDepartmentNames() {
  return api.get<string[]>('/departments/names')
}

export function createDepartment(data: DepartmentForm) {
  return api.post<Department>('/departments', data)
}

export function updateDepartment(id: number, data: Partial<DepartmentForm>) {
  return api.put<Department>(`/departments/${id}`, data)
}

export function deleteDepartment(id: number) {
  return api.delete(`/departments/${id}`)
}

export function reorderDepartments(items: ReorderItem[]) {
  return api.put('/departments/reorder', items)
}

export function seedDeptTree() {
  return api.post('/departments/seed-tree')
}

// ─── Position Level API ─────────────────────────────────────

export function fetchPositionLevels() {
  return api.get<PositionLevelMap>('/position-levels')
}

// ─── Photo ──────────────────────────────────────────────────

export function getPhotoUrl(filename: string) {
  return `/api/photo/${encodeURIComponent(filename)}`
}

// ─── Test API ───────────────────────────────────────────────

export function checkAnswers(answers: AnswerItem[]) {
  return api.post<CheckResult>('/test/check', { answers })
}

export function saveTestResult(total: number, correct: number, score: number) {
  return api.post('/test/results', { total, correct, score })
}

// ─── Rescan ─────────────────────────────────────────────────

export function rescan() {
  return api.post('/rescan')
}

// ─── Import API ─────────────────────────────────────────────

export function importExcel(dryRun?: boolean) {
  return api.post('/import-excel', null, { params: { dry_run: dryRun || false } })
}

export function importLeaders() {
  return api.post('/import-markdown-leaders')
}

// ─── Meeting API ────────────────────────────────────────────

export interface Meeting {
  id: number
  name: string
  input_persons?: string | null
  input_departments?: string | null
  sorted_persons?: string | null  // JSON string
  sorted_departments?: string | null  // JSON string
  sort_snapshot_id?: number | null  // 使用的部门排序存档ID
  created_at?: string | null
}

export interface MeetingCreate {
  name: string
  input_persons?: string | null
  input_departments?: string | null
  sort_snapshot_id?: number | null
}

export interface MeetingUpdate {
  name?: string | null
  input_persons?: string | null
  input_departments?: string | null
  sort_snapshot_id?: number | null
}

export function createMeeting(data: MeetingCreate) {
  return api.post<Meeting>('/meetings', data)
}

export function fetchMeetings(params?: {
  search?: string
  date_from?: string
  date_to?: string
  department?: string
  person?: string
}) {
  return api.get<Meeting[]>('/meetings', { params })
}

export function fetchMeeting(id: number) {
  return api.get<Meeting>(`/meetings/${id}`)
}

export function updateMeeting(id: number, data: MeetingUpdate) {
  return api.put<Meeting>(`/meetings/${id}`, data)
}

export function deleteMeeting(id: number) {
  return api.delete(`/meetings/${id}`)
}

export function resortMeeting(id: number, data?: { sort_snapshot_id?: number | null }) {
  return api.post<Meeting>(`/meetings/${id}/resort`, data || {})
}

// ─── Department Sort Snapshot (部门排序存档) API ─────────────

export interface DeptSnapshot {
  id: number
  name: string
  note?: string | null
  data?: string | null  // JSON string of captured tree
  created_at?: string | null
}

export interface DeptSnapshotForm {
  name: string
  note?: string | null
  recapture?: boolean | null
}

export function fetchDeptSnapshots() {
  return api.get<DeptSnapshot[]>('/dept-snapshots')
}

export function fetchDeptSnapshot(id: number) {
  return api.get<DeptSnapshot>(`/dept-snapshots/${id}`)
}

export function createDeptSnapshot(data: DeptSnapshotForm) {
  return api.post<DeptSnapshot>('/dept-snapshots', data)
}

export function updateDeptSnapshot(id: number, data: Partial<DeptSnapshotForm>) {
  return api.put<DeptSnapshot>(`/dept-snapshots/${id}`, data)
}

export function deleteDeptSnapshot(id: number) {
  return api.delete(`/dept-snapshots/${id}`)
}

export function applyDeptSnapshot(id: number) {
  return api.post(`/dept-snapshots/${id}/apply`)
}

// ─── 登录鉴权 ─────────────────────────────────────────────

export interface UserInfo {
  id: number
  username: string
  role: 'admin' | 'user'
  display_name?: string | null
}

export interface LoginResult {
  token: string
  user: UserInfo
}

const TOKEN_KEY = 'ea_token'
const USER_KEY = 'ea_user'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
export function getStoredUser(): UserInfo | null {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}
export function setStoredUser(user: UserInfo) {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function login(username: string, password: string) {
  return api.post<{ code: number; data: LoginResult }>('/auth/login', { username, password })
}
export function logout() {
  return api.post('/auth/logout')
}
export function fetchMe() {
  return api.get<{ code: number; data: UserInfo }>('/auth/me')
}
export function changePassword(oldPassword: string, newPassword: string) {
  return api.post('/auth/change-password', { old_password: oldPassword, new_password: newPassword })
}

// ─── 拦截器：携带 token；401 统一跳登录 ───────────────────
api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error.response?.status
    const url: string = error.config?.url || ''
    if (status === 401 && !url.startsWith('/auth/login')) {
      clearToken()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)
