import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export const API_URL = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class ApiService {

    constructor(private http: HttpClient) { }

    // ── Auth ──────────────────────────────────────────────────────────────────

    login(email: string, password: string): Observable<any> {
        return this.http.post(`${API_URL}/auth/login`, { email, password });
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

    // ── Gym Visits ────────────────────────────────────────────────────────────

    getGymVisits(userId: string): Observable<any> {
        return this.http.get(`${API_URL}/users/${userId}/gym-visits`);
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

    validatePRVideo(userId: string, videoFile: File): Observable<any> {
        const formData = new FormData();
        formData.append('video', videoFile);
        return this.http.post(`${API_URL}/users/${userId}/lifting-prs/validate-video`, formData);
    }

    // ── Challenges ────────────────────────────────────────────────────────────

    getDailyChallenge(): Observable<any> {
        return this.http.get(`${API_URL}/challenges/daily`);
    }

    // ── Ranking ───────────────────────────────────────────────────────────────

    getRanking(): Observable<any> {
        return this.http.get(`${API_URL}/ranking`);
    }
}