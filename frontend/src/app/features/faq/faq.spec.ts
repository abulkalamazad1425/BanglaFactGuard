import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { FaqComponent } from './faq';
import { APP_ROUTES } from '../../routes/app.routes';
import { NavbarComponent } from '../../shared/components/navbar/navbar.component';
import { FooterComponent } from '../../shared/components/footer/footer.component';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';

describe('FaqComponent', () => {
  it('is reachable at /faq through the application routes', async () => {
    TestBed.configureTestingModule({ providers: [provideRouter(APP_ROUTES), provideHttpClient(), provideHttpClientTesting()] });
    const harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/faq');
    harness.detectChanges();
    expect(TestBed.inject(Router).url).toBe('/faq');
    // The FAQ is lazy-loaded inside the main layout's router outlet.
    expect(harness.fixture.nativeElement.querySelector('app-faq')).not.toBeNull();
    expect(harness.fixture.nativeElement.textContent).toContain('How results are produced');
  });

  it('answers every required topic with a linkable section', () => {
    TestBed.configureTestingModule({ imports: [FaqComponent], providers: [provideRouter([])] });
    const fixture = TestBed.createComponent(FaqComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    for (const id of ['headline-alteration', 'matched-altered', 'source-not-found', 'body-scores', 'score-range',
      'not-a-verdict', 'unavailable', 'photocard']) {
      expect(el.querySelector(`#${id}`)).withContext(id).not.toBeNull();
    }
    const text = el.textContent ?? '';
    for (const phrase of ['TF-IDF cosine similarity', 'Jaccard similarity', 'Normalized Levenshtein similarity',
      'LaBSE', 'not BERTScore', 'not proof that the claim is false', 'up to three attempts', 'EasyOCR', 'never the article body']) {
      expect(text).withContext(phrase).toContain(phrase);
    }
    expect(text).not.toMatch(/\?\s*Source not found/);
  });

  it('is linked from the footer, not the navigation bar', () => {
    TestBed.configureTestingModule({
      imports: [NavbarComponent, FooterComponent],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    const links = (cmp: any) => {
      const fixture = TestBed.createComponent(cmp);
      fixture.detectChanges();
      return Array.from((fixture.nativeElement as HTMLElement).querySelectorAll('a')).map((a) => a.getAttribute('href'));
    };
    expect(links(FooterComponent)).toContain('/faq');
    expect(links(NavbarComponent)).not.toContain('/faq');
  });
});
