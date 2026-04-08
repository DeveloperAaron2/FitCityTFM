import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment.development';

export const API_URL = environment.API_URL;

@Injectable({ providedIn: 'root' })
export class ApiService {

    constructor(private http: HttpClient) { }

    // ── Auth ──────────────────────────────────────────────────────────────────

    login(email: string, password: string): Observable<any> {
        return this.http.post(`${API_URL}/auth/login`, { email, password });
    }

    googleCallback(accessToken: string, refreshToken: string): Observable<any> {
        return this.http.post(`${API_URL}/auth/google/callback`, { access_token: accessToken, refresh_token: refreshToken });
    }

    register(email: string, password: string, username: string, handle: string): Observable<any> {
        return this.http.post(`${API_URL}/auth/register`, { email, password, username, handle });
    }

    logout(): Observable<any> {
        return this.http.post(`${API_URL}/auth/logout`, {});
    }

    // ── Users ─────────────────────────────────────────────────────────────────

    getUser(userId: string): Observable<any> {
        return this.http.get(`${API_URL}/users/${userId}`);
    }

    addXP(userId: string, xpToAdd: number): Observable<any> {
        return this.http.put(`${API_URL}/users/${userId}/xp`, { xp_to_add: xpToAdd });
    }

    uploadAvatar(userId: string, file: File): Observable<{ avatar_url: string }> {
        const formData = new FormData();
        formData.append('file', file);
        return this.http.put<{ avatar_url: string }>(`${API_URL}/users/${userId}/avatar`, formData);
    }

    // ── Gym Visits ────────────────────────────────────────────────────────────

    getGymVisits(userId: string): Observable<any> {
        return this.http.get(`${API_URL}/users/${userId}/gym-visits`);
    }

    createGymVisit(userId: string, body: { gym_name: string, gym_address?: string, gym_lat?: number, gym_lon?: number }): Observable<any> {
        return this.http.post(`${API_URL}/users/${userId}/gym-visits`, body);
    }

    getGymStats(userId: string): Observable<any> {
        return this.http.get(`${API_URL}/users/${userId}/gym-visits/stats`);
    }

    // ── Lifting PRs ───────────────────────────────────────────────────────────

    getLiftingPRs(userId: string): Observable<any> {
        return this.http.get(`${API_URL}/users/${userId}/lifting-prs`);
    }

    createLiftingPR(userId: string, body: { gym_name: string, exercise_name: string, exercise_emoji: string, weight_kg: number, reps: number }): Observable<any> {
        return this.http.post(`${API_URL}/users/${userId}/lifting-prs`, body);
    }

    validatePRVideo(userId: string, videoFile: File, exerciseName: string, gymName: string = '', weightKg: number = 0, reps: number = 1): Observable<any> {
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('exercise_name', exerciseName);
        formData.append('gym_name', gymName);
        formData.append('weight_kg', weightKg.toString());
        formData.append('reps', reps.toString());
        return this.http.post(`${API_URL}/users/${userId}/lifting-prs/validate-video`, formData);
    }

    /** Standalone AI validation — no user/gym association, no storage */
    validateVideoOnly(videoFile: File, exerciseName: string): Observable<any> {
        const formData = new FormData();
        formData.append('video', videoFile);
        formData.append('exercise_name', exerciseName);
        return this.http.post(`${API_URL}/validate-video`, formData);
    }

    // ── Challenges ────────────────────────────────────────────────────────────

    getDailyChallenge(): Observable<any> {
        return this.http.get(`${API_URL}/challenges/daily`);
    }

    getUserChallengesAll(userId: string): Observable<any[]> {
        return this.http.get<any[]>(`${API_URL}/users/${userId}/challenges/all`);
    }

    updateChallengeProgress(userId: string, challengeId: string, progress: number): Observable<any> {
        return this.http.post(`${API_URL}/users/${userId}/challenges/${challengeId}/progress`, { progress });
    }

    // ── Ranking ───────────────────────────────────────────────────────────────

    getRanking(): Observable<any> {
        return this.http.get(`${API_URL}/ranking`);
    }

    getGlobalPrsRanking(): Observable<any> {
        return this.http.get(`${API_URL}/ranking/prs`);
    }

    getGymPrsRanking(): Observable<any> {
        return this.http.get(`${API_URL}/ranking/prs/by-gym`);
    }

    getGymBestLifts(gymName: string): Observable<any[]> {
        return this.http.get<any[]>(`${API_URL}/ranking/prs/by-gym/${encodeURIComponent(gymName)}/best-lifts`);
    }

    // ── PR Reports ────────────────────────────────────────────────────────────

    reportPR(prId: string, reporterId: string, reason: string = 'weight_mismatch'): Observable<any> {
        return this.http.post(`${API_URL}/prs/${prId}/report`, { reporter_id: reporterId, reason });
    }

    getPRReportCount(prId: string): Observable<any> {
        return this.http.get(`${API_URL}/prs/${prId}/reports/count`);
    }
}