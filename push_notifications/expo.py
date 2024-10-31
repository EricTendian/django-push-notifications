"""
Expo Notifications API
Specific to Expo apps, a platform-agnostic notification service which uses FCM/APNS under the hood.
https://docs.expo.dev/push-notifications/overview/
"""

from copy import copy
from typing import Dict, List

from exponent_server_sdk import (
	DeviceNotRegisteredError,
	PushClient,
	PushMessage,
	PushTicket,
)
import requests

from .conf import get_manager


def _validate_exception_for_deactivation(response: PushTicket) -> bool:
	try:
		response.validate_response()
		return False
	except DeviceNotRegisteredError:
		return True
	except:
		return False

def _deactivate_devices_with_error_results(
	registration_ids: List[str],
	results: List[PushTicket],
) -> List[str]:
	if not results:
		return []
	deactivated_ids = [
		token
		for item, token in zip(results, registration_ids)
		if _validate_exception_for_deactivation(item)
	]
	from .models import ExpoDevice
	ExpoDevice.objects.filter(registration_id__in=deactivated_ids).update(active=False)
	return deactivated_ids


def _prepare_message(message: PushMessage, token: str):
	return message._replace(to=token)


def _get_client(application_id):
	session = requests.Session()
	session.headers.update(
		{
			"accept": "application/json",
			"accept-encoding": "gzip, deflate",
			"content-type": "application/json",
		}
	)
	if application_id:
		access_token = get_manager().get_expo_access_token(application_id)
		if access_token:
			session.headers.update({"Authorization": f"Bearer {access_token}"})

	return PushClient(session=session)


def send_message(
	registration_ids,
	message: PushMessage,
	application_id=None,
	**kwargs
):
	"""
	Sends an Expo notification to one or more registration_ids. The registration_ids
	can be a list or a single string.

	:param registration_ids: A list of registration ids or a single string
	:param message: The PushMessage object
	:param application_id: The application id to use.

	:return: An object with the results of the send operation
	"""
	client = _get_client(application_id)

	# Checks for valid recipient
	if registration_ids is None and message.body is None:
		return

	# Bundles the registration_ids in an list if only one is sent
	if not isinstance(registration_ids, list):
		registration_ids = [registration_ids] if registration_ids else None

	results: Dict[str, str] = {}
	if registration_ids:
		messages = [
			_prepare_message(message, token) for token in registration_ids
		]
		responses = client.publish_multiple(messages)
		_deactivate_devices_with_error_results(registration_ids, responses)
		# receipts = client.check_receipts_multiple(responses)
		for registration_id, response in zip(registration_ids, responses):
			results[registration_id] = "Success" if response.is_success() else (response.details.get('error', response.status) if response.details else response.status)
	return results


send_bulk_message = send_message
