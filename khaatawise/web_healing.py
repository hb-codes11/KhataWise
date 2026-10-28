"""Browser-only controls and a bounded expense recovery demonstration."""
from decimal import Decimal, InvalidOperation
import requests
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

REPO = 'hb-codes11/KhataWise'
WORKFLOW = 'self-heal.yml'
ACTIONS_URL = f'https://github.com/{REPO}/actions/workflows/{WORKFLOW}'


def healer_page(request):
    return render(request, 'khaatawise/healer.html', {'actions_url': ACTIONS_URL})


def cloud_status(request):
    data = cache.get('cloud-healing-runs')
    if data is None:
        try:
            response = requests.get(f'https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs',
                                    params={'per_page': 8}, timeout=5,
                                    headers={'Accept': 'application/vnd.github+json'})
            response.raise_for_status()
            runs = response.json()['workflow_runs']
            data = {'available': True, 'runs': [
                {key: run.get(key) for key in ('id', 'status', 'conclusion', 'html_url', 'created_at', 'event')}
                for run in runs], 'actions_url': ACTIONS_URL}
            cache.set('cloud-healing-runs', data, 20)
        except (requests.RequestException, ValueError, KeyError):
            data = {'available': False, 'runs': [], 'actions_url': ACTIONS_URL,
                    'message': 'Cloud run status is temporarily unavailable. Open GitHub runs for details.'}
    return JsonResponse(data)


def expense_recovery_demo():
    # No database writes, shell, model commands, credentials, or uploaded code.
    payload = {'amount': '1,250.00', 'category': None, 'currency': 'INR'}
    events = []
    for iteration in range(1, 4):
        try:
            amount = Decimal(payload['amount'])
            category = payload['category'].strip()
            if amount <= 0 or not category:
                raise ValueError('Invalid expense')
            events.append({'iteration': iteration, 'phase': 'verified', 'message': 'Expense accepted: INR 1250.00, category Other.'})
            return {'status': 'resolved', 'iterations': iteration, 'events': events,
                    'verification': {'amount': str(amount), 'category': category, 'production_data_changed': False},
                    'scope': 'Isolated payload demo. This does not change production source code or your books.'}
        except InvalidOperation:
            events.append({'iteration': iteration, 'phase': 'detected', 'message': 'InvalidOperation: formatted amount cannot be parsed.'})
            payload['amount'] = payload['amount'].replace(',', '')
            events.append({'iteration': iteration, 'phase': 'patched', 'message': 'Normalized the amount and retried the expense.'})
        except AttributeError:
            events.append({'iteration': iteration, 'phase': 'detected', 'message': 'AttributeError: category is missing.'})
            payload['category'] = 'Other'
            events.append({'iteration': iteration, 'phase': 'patched', 'message': 'Applied the fallback category and retried the expense.'})
    return {'status': 'verification_failed', 'events': events}


@require_POST
def recovery_demo(request):
    return JsonResponse(expense_recovery_demo())
