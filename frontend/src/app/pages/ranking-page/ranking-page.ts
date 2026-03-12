import { ChangeDetectionStrategy, Component } from '@angular/core';

@Component({
    selector: 'app-ranking-page',
    standalone: true,
    template: `<p style="color:#fff;padding:16px">Página de ranking — en construcción 🏆</p>`,
    changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RankingPage { }
