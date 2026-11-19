import { api } from './client'
import type {
  AccessTokenResponse,
  MessageResponse,
  Profile,
  ProfileUpdate,
  UserGroup,
  UserList,
} from './types'

export function register(email: string, password: string) {
  return api('/accounts/register', { method: 'POST', body: { email, password } })
}

export function activate(token: string) {
  return api<MessageResponse>('/accounts/activation', { method: 'POST', body: { token } })
}

export function resendActivation(email: string) {
  return api<MessageResponse>('/accounts/activation/resend', { method: 'POST', body: { email } })
}

// The refresh token arrives as an httpOnly cookie; the access token - in the body.
export function login(email: string, password: string) {
  return api<AccessTokenResponse>('/accounts/login', {
    method: 'POST',
    body: { email, password },
  })
}

export function logout() {
  return api('/accounts/logout', { method: 'POST' })
}

export function changePassword(oldPassword: string, newPassword: string) {
  return api<MessageResponse>('/accounts/change-password', {
    method: 'POST',
    body: { old_password: oldPassword, new_password: newPassword },
  })
}

export function requestPasswordReset(email: string) {
  return api<MessageResponse>('/accounts/password-reset/request', {
    method: 'POST',
    body: { email },
  })
}

export function completePasswordReset(token: string, newPassword: string) {
  return api<MessageResponse>('/accounts/password-reset/complete', {
    method: 'POST',
    body: { token, new_password: newPassword },
  })
}

export function getProfile() {
  return api<Profile>('/accounts/profile')
}

export function updateProfile(data: ProfileUpdate) {
  return api<Profile>('/accounts/profile', { method: 'PATCH', body: data })
}

export function uploadAvatar(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return api<Profile>('/accounts/profile/avatar', { method: 'PUT', formData })
}

// --- admin ---

export function listUsers(page: number, pageSize: number) {
  return api<UserList>('/accounts/users', { query: { page, page_size: pageSize } })
}

export function changeUserGroup(userId: number, group: UserGroup) {
  return api<MessageResponse>(`/accounts/users/${userId}/group`, {
    method: 'PATCH',
    body: { group },
  })
}

export function activateUser(userId: number) {
  return api<MessageResponse>(`/accounts/users/${userId}/activate`, { method: 'POST' })
}
