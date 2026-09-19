/**
 * Message Interpolator - Handles template interpolation with contact data
 * Responsible for: replacing {nome}, {telefone}, {email}, etc. in templates
 */
class MessageInterpolator {
    /**
     * Interpolate template variables with contact data
     * @param {string} text 
     * @param {object} data 
     * @returns {string} 
     */
    interpolate(text, data) {
        if (!text) return "";
        return text.replace(/{nome}/gi, data.name || "")
            .replace(/{telefone}/gi, data.phone || "")
            .replace(/{email}/gi, data.email || "")
            .replace(/{origem}/gi, data.origem || "")
            .replace(/{interesse}/gi, data.interesse || "")
            .replace(/{observacao}/gi, data.observacao || "")
            .replace(/{variavel}/gi, data.variable || "");
    }

    /**
     * Format phone number
     * @param {string} phone 
     * @returns {string} 
     */
    formatPhone(phone) {
        if (!phone) return "";
        const digits = phone.replace(/\D/g, '');
        if (digits.length === 10 || digits.length === 11) return '55' + digits;
        return phone;
    }

    /**
     * Get template by variant
     * @param {string} variant 
     * @param {object} templates 
     * @returns {string} 
     */
    getTemplate(variant, templates) {
        return templates[variant] || templates['A'] || "";
    }
}

export default MessageInterpolator;