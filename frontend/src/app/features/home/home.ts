import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';
import { VERIFY_OPTIONS } from '../verification/verify-facts/verify-options';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './home.html',
  styleUrls: ['./home.scss']
})
export class HomeComponent {
  readonly options = VERIFY_OPTIONS;

  readonly verdicts = [
    { label: 'Real', cls: 'badge-true', desc: 'Experts found the claim accurate.' },
    { label: 'Fake', cls: 'badge-false', desc: 'Experts found the claim false.' },
    { label: 'Altered', cls: 'badge-partial', desc: 'Experts found material changes to the original content.' },
    { label: 'Misleading', cls: 'badge-partial', desc: 'Experts found the claim gives a misleading impression.' },
  ];
}
