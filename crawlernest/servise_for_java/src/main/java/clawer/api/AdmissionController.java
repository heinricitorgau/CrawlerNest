package clawer.api;

import clawer.dto.AdmissionDTO;
import clawer.service.AdmissionService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/admissions")
public class AdmissionController {

    private final AdmissionService admissionService;

    public AdmissionController(AdmissionService admissionService) {
        this.admissionService = admissionService;
    }

    @GetMapping
    public List<AdmissionDTO> getAllAdmissions() {
        return admissionService.getAllAdmissions();
    }
}
