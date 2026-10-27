// Email OTP before a web form saves an Employee Checkin or Leave Application.
// The server checks the token again in centhr.api.otp.web_form.validate_web_form_otp.
frappe.ready(() => {
	const web_form = frappe.web_form;
	if (!web_form || !web_form.is_new) return;

	const METHOD = "centhr.api.otp.web_form";
	const save = web_form.save.bind(web_form);
	let token = null;

	web_form.save = () => {
		if (token) {
			web_form.doc.otp_token = token;
			return save();
		}

		// Show missing fields and the form's own checks before sending a code
		if (!web_form.get_values(web_form.allow_incomplete, true)) return false;
		if (web_form.validate && web_form.validate() === false) return false;

		const employee = web_form.get_value("employee");
		send_code(employee).then((email) => email && ask_code(employee, email));
		return false;
	};

	web_form.after_save = () => {
		token = null;
		delete web_form.doc.otp_token;
	};

	function send_code(employee) {
		return frappe
			.call({ method: `${METHOD}.send_otp`, args: { employee }, freeze: true })
			.then((r) => r.message);
	}

	function ask_code(employee, email) {
		const dialog = new frappe.ui.Dialog({
			title: __("Verify Your Email"),
			fields: [
				{
					fieldtype: "HTML",
					options: `<p>${__("Enter the code sent to {0}.", [frappe.utils.escape_html(email)])}</p>`,
				},
				{ fieldname: "otp", fieldtype: "Data", label: __("Code"), reqd: 1 },
			],
			primary_action_label: __("Verify and Submit"),
			primary_action: ({ otp }) => {
				frappe
					.call({ method: `${METHOD}.verify_otp`, args: { employee, otp }, freeze: true })
					.then((r) => {
						token = r.message;
						dialog.hide();
						web_form.save();
					});
			},
			secondary_action_label: __("Resend Code"),
			secondary_action: () => {
				dialog.set_value("otp", "");
				send_code(employee).then(() => frappe.show_alert(__("A new code was sent")));
			},
		});
		dialog.show();
		// Website pages lack the desk CSS that hides the fieldname tooltip
		dialog.$wrapper.find(".tooltip-content").addClass("hidden");
	}
});
